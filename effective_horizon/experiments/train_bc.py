import faulthandler
import os
import signal
from logging import Logger

import ray
import torch
from ray.rllib.algorithms import Algorithm
from ray.rllib.utils.typing import AlgorithmConfigDict, ModelConfigDict
from ray.tune.registry import ENV_CREATOR, _global_registry
from sacred import SETTINGS as sacred_settings
from sacred import Experiment

from effective_horizon.envs.procgen import DeterministicProcgenEnv

from ..agents.bc import BC
from ..training_utils import build_logger_creator

ex = Experiment("train_bc")
sacred_settings.CONFIG.READ_ONLY_CONFIG = False


# Useful for debugging.
faulthandler.register(signal.SIGUSR1)


@ex.config
def sacred_config(_log):  # noqa
    # Environment
    env_name = "MiniGrid-Empty-5x5-v0"
    env_config: dict = {}

    _env = _global_registry.get(ENV_CREATOR, env_name)(env_config)

    # Training
    num_workers = 2
    num_envs_per_worker = 1
    seed = 0
    num_gpus = 1 if torch.cuda.is_available() else 0
    simple_optimizer = False
    compress_observations = True
    train_batch_size = 2000
    count_batch_size_by = "timesteps"
    sgd_minibatch_size = 500
    num_training_iters = 500  # noqa: F841
    lr = 1e-3
    grad_clip = None
    entropy_coeff = 0
    validation_prop = 0
    input = ""

    # Model
    custom_model = None
    vf_share_layers = False
    model_config: ModelConfigDict = {
        "custom_model": custom_model,
        "custom_model_config": {},
        "vf_share_layers": vf_share_layers,
        "max_seq_len": 1,
    }
    if isinstance(_env, DeterministicProcgenEnv):
        model_config["conv_filters"] = [
            (16, (8, 8), 4),
            (32, (4, 4), 2),
            (256, (8, 8), 1),
        ]

    # Logging
    save_freq = 25  # noqa: F841
    log_dir = "data/logs"  # noqa: F841
    experiment_tag = None
    experiment_name_parts = ["bc", env_name]
    if custom_model is not None:
        experiment_name_parts.append(custom_model)
    if experiment_tag is not None:
        experiment_name_parts.append(experiment_tag)
    experiment_name = os.path.join(*experiment_name_parts)  # noqa: F841

    # Evaluation
    evaluation_num_workers = 2
    evaluation_interval = 25
    evaluation_duration = 10
    evaluation_duration_unit = "episodes"
    evaluation_explore = True
    evaluation_config = {
        "input": "sampler",
        "explore": evaluation_explore,
    }

    config: AlgorithmConfigDict = {  # noqa: F841
        "env": env_name,
        "env_config": env_config,
        "num_workers": num_workers,
        "num_envs_per_worker": num_envs_per_worker,
        "num_gpus": num_gpus,
        "simple_optimizer": simple_optimizer,
        "compress_observations": compress_observations,
        "train_batch_size": train_batch_size,
        "batch_mode": "complete_episodes"
        if count_batch_size_by == "episodes"
        else "truncate_episodes",
        "seed": seed,
        "model": model_config,
        "framework": "torch",
        "input": input,
        "grad_clip": grad_clip,
        "lr": lr,
        "train_batch_size": train_batch_size,
        "sgd_minibatch_size": sgd_minibatch_size,
        "validation_prop": validation_prop,
        "entropy_coeff": entropy_coeff,
        "evaluation_num_workers": evaluation_num_workers,
        "evaluation_interval": evaluation_interval,
        "evaluation_duration": evaluation_duration,
        "evaluation_duration_unit": evaluation_duration_unit,
        "evaluation_config": evaluation_config,
    }


@ex.automain
def main(
    config,
    log_dir,
    experiment_name,
    num_training_iters,
    save_freq,
    _log: Logger,
):
    ray.init(
        ignore_reinit_error=True,
        include_dashboard=False,
    )

    trainer: Algorithm = BC(
        config,
        logger_creator=build_logger_creator(
            log_dir,
            experiment_name,
        ),
    )

    result = None
    for train_iter in range(num_training_iters):
        _log.info(f"Starting training iteration {trainer.iteration}")
        result = trainer.train()

        if trainer.iteration % save_freq == 0:
            checkpoint = trainer.save()
            _log.info(f"Saved checkpoint to {checkpoint}")

    checkpoint = trainer.save()
    _log.info(f"Saved final checkpoint to {checkpoint}")

    return result
