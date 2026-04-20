from rewards_36_up import *

rewards_sets = []

for i in range(36,99):
    rewards_sets.append("REWARDS_SET_" + str(i))

for reward_set in rewards_sets:
    suffix = reward_set[-2:]
    rare_rewards_set_name = "RARE_REWARDS_SET_" + suffix
    exec(rare_rewards_set_name + " = []")

    content = eval(reward_set)
    working_list = []
    for item in content:
        item_name = item["item_name"]
        res = 0
        for thing in content:
            if thing["item_name"] == item_name:
                res += 1
        if res <= 5:
            if item not in working_list:
                working_list.append(item)
    for final_item in working_list:
        exec(rare_rewards_set_name + ".append(final_item)")
    
    print(rare_rewards_set_name + " = ")
    exec("print(" + rare_rewards_set_name + ")")