import os

import torch
import gym

from ppo import (
    PPO,
    PPOTrainingParameters,
    DeepPolicy,
    collect_trajectories_serial,
    TabularPolicy,
    collect_trajectories_parallel,
)

from envs.tabular_world import TabularWorld


################################## set device ##################################

print(
    "============================================================================================"
)


# set device to cpu or cuda
device = torch.device("cpu")

if torch.cuda.is_available():
    device = torch.device("cuda:0")
    torch.cuda.empty_cache()
    print("Device set to : " + str(torch.cuda.get_device_name(device)))
else:
    print("Device set to : cpu")

print(
    "============================================================================================"
)


print(
    "============================================================================================"
)

# env_name = "CartPole-v1"
# has_continuous_action_space = False
# action_std = None
# random_seed = 0  # set random seed if required (0 = no random seed)
# env = gym.make(env_name)


env_name = "MiniGrid-FourRooms-v0"
data_dir = "data/"
file_name = f"{data_dir}/{env_name}/consolidated.npz"
random_seed = 0  # set random seed if required (0 = no random seed)
env = TabularWorld(file_name, num_worlds=4096, device=device)

print("training environment name : " + env_name)


###################### logging ######################

#### log files for multiple runs are NOT overwritten

log_dir = "PPO_logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_dir = log_dir + "/" + env_name + "/"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)


#### get number of log files in log directory
run_num = 0
current_num_files = next(os.walk(log_dir))[2]
run_num = len(current_num_files)


#### create new log file for each run
log_f_name = log_dir + "/PPO_" + env_name + "_log_" + str(run_num) + ".csv"

print("current logging run number for " + env_name + " : ", run_num)
print("logging at : " + log_f_name)

#####################################################


################### checkpointing ###################

run_num_pretrained = (
    0  #### change this to prevent overwriting weights in same env_name folder
)

directory = "PPO_preTrained"
if not os.path.exists(directory):
    os.makedirs(directory)

directory = directory + "/" + env_name + "/"
if not os.path.exists(directory):
    os.makedirs(directory)


checkpoint_path = directory + "PPO_{}_{}_{}.pth".format(
    env_name, random_seed, run_num_pretrained
)
print("save checkpoint path : " + checkpoint_path)

#####################################################


# params = PPOTrainingParameters(
#     max_training_timesteps=int(1e5),
#     max_ep_len=400,
#     update_timestep=1600,
#     K_epochs=40,
#     eps_clip=0.2,
#     gamma=0.99,
#     lr_actor=0.0003,
#     lr_critic=0.001,
# )


# def policy_factory():
#     return DeepPolicy(
#         state_dim=env.observation_space.shape[0],
#         action_dim=env.action_space.shape[0]
#         if has_continuous_action_space
#         else env.action_space.n,
#         has_continuous_action_space=has_continuous_action_space,
#         action_std_init=action_std,
#         device=device,
#     )


params = PPOTrainingParameters(
    max_training_timesteps=int(1e8),
    max_ep_len=200,
    update_timestep=env.num_worlds * 200,
    K_epochs=10,
    eps_clip=0.2,
    gamma=0.95,
    lr_actor=0.0003,
    lr_critic=0.001,
    update_batch_size=4096 * 8,
)


def policy_factory():
    return TabularPolicy(
        num_states=env.num_states,
        num_actions=3,  # env.num_actions,
        device=device,
    )


# initialize a PPO agent
ppo_agent = PPO(
    policy_builder=policy_factory,
    collect_trajectory_fn=collect_trajectories_parallel,
    params=params,
    device=device,
)

print(
    "============================================================================================"
)
print(f"Num states: {env.num_states}")
print(f"Num actions: {env.num_actions}")
print(
    "============================================================================================"
)

ppo_agent.train(
    env=env,
    print_freq=1,
    log_freq=1,
    save_model_freq=20000,
    log_f_name=log_f_name,
    checkpoint_path=checkpoint_path,
)
