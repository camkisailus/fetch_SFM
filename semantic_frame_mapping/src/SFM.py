#! /usr/bin/python3

import rospy

from particle_filters import *
from utils import *
from std_msgs.msg import Bool
from geometry_msgs.msg import Point
from std_msgs.msg import String
from fetch_actions.msg import MoveBaseRequestAction, MoveBaseRequestGoal, TorsoControlRequestAction, TorsoControlRequestGoal, PointHeadRequestAction, PointHeadRequestGoal, PickRequestAction, PickRequestGoal

# room number: min_x, max_x, min_y, max_y, min_z, max_z
# REGIONS = {
#     'table1': (0, 1, 0, 1, 0, 1),
#     'table2': (5, 6, 5, 6, 5, 6),
# }
# REGIONS = {
#     'table1': (-2, -3, -5, -4, 0.5, 1.5),
#     'table2': (5, 6, 5, 6, 5, 6),
# }
## LAB 06-21-22
REGIONS = {
    'table1': (-2.2, -1.2, -1.25, -0.5, 0.6, 0.8),
    'table2': (-5.75, -4.75, -2.25, -1.5, 0.6, 0.8),
    'elevator': (-1.2, -1.2, -18.5, -18.5, 1, 1),
}
## LAB HALLWAY
# ELEVATOR = (-1.0, -18.7, 3.14)

## LAB 07-21-22
# REGIONS = {
#     'elevator':(-4.5, -4.2, -1.2, -1.5, 0, 1)
# }

## LAB 07-24-22
# REGIONS = {
#     'elevator': (5.5, 5.6, 0.8, 1.2, 0, 2)
# }

## HALLWAY 07-24-22
# REGIONS = {
#     'elevator': (-7, -8, 18, 19, 0, 3)
# }
class State():
    def __init__(self):
        self.action_history = ['idle']
        self.ah_sub = rospy.Subscriber("/add_action_to_action_history", String, self.add_action_to_action_history)
    
    def add_action_to_action_history(self, action_taken):
        self.action_history.append(action_taken.data)

class Region():
    def __init__(self, name, min_x, max_x, min_y, max_y, min_z, max_z):
        self.name = name
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.min_z = min_z
        self.max_z = max_z
    
    def get_bounds(self):
        return (self.min_x, self.max_x, self.min_y, self.max_y, self.min_z, self.max_z)

class ActionClient():
    def __init__(self):
        self.move_base_client = actionlib.SimpleActionClient("kisailus_move_base", MoveBaseRequestAction)
        self.torso_client = actionlib.SimpleActionClient("kisailus_torso_controller", TorsoControlRequestAction)
        self.point_head_client = actionlib.SimpleActionClient("kisailus_point_head", PointHeadRequestAction)
        self.pick_client = actionlib.SimpleActionClient("kisailus_pick", PickRequestAction)
        self.grasp_pub = rospy.Publisher('request_grasp_pts', Bool, queue_size=10)
        self.point_head_pub = rospy.Publisher('/point_head/at', Point, queue_size=10)
        
    def go_to(self, x, y, theta):
        request = MoveBaseRequestGoal()
        request.x = x
        request.y = y
        request.theta = theta
        self.move_base_client.send_goal(request)
        self.move_base_client.wait_for_result()

    def move_torso(self, height):
        request = TorsoControlRequestGoal()
        request.height = height
        self.torso_client.send_goal(request)
        self.torso_client.wait_for_result()
    
    def point_head(self, x, y, z):
        request = PointHeadRequestGoal()
        request.x = x
        request.y = y
        request.z = z
        self.point_head_client.send_goal(request)
        self.point_head_client.wait_for_result()
    
    def pick(self, mode=0, goal=None):
        if mode == 1:
            assert(goal is not None)
            request.goal = goal
        request = PickRequestGoal()
        request.mode = mode
        self.pick_client.send_goal(request)
        rospy.loginfo("Sent pick_client goal")
        self.pick_client.wait_for_result()
        
    
    
class SFMClient():
    def __init__(self):
        self.kb = init_knowledge_base(rospy.get_param('~sf_dir'))
        self.execute_frame_sub = rospy.Subscriber("/execute", String, self.execute_frame)
        self.ac = ActionClient()
        self.regions = {}
        for name, bounds in REGIONS.items():
            self.regions[name] = Region(name, bounds[0], bounds[1],bounds[2], bounds[3], bounds[4], bounds[5])
        self.bottle_particle_filter = ObjectParticleFilter(50, valid_regions=[self.regions['table1'], self.regions['table2']], label='bottle')
        self.bowl_particle_filter = ObjectParticleFilter(50, valid_regions=[self.regions['table1']], label='bowl')
        self.spoon_particle_filter = ObjectParticleFilter(50, valid_regions=[self.regions['table1'], self.regions['table2']], label='spoon')
        self.object_filters = {'bottle':self.bottle_particle_filter, 'bowl':self.bowl_particle_filter, 'spoon':self.spoon_particle_filter}
        self.state = State()
        self.frame_filters = {}
        self.frame_to_label_dict = {}
        self.update = True
        for i, frame in enumerate(self.kb):
            self.frame_to_label_dict[i] = frame.name
            valid_regions = None
            # valid_regions = [self.regions['table1'], self.regions['table2']]
            # if frame.name.startswith('go_elevator'):
            # valid_regions = [self.regions['elevator']]
            filter = FrameParticleFilter(50, frame.name, frame.preconditions, frame.core_frame_elements, valid_regions)
            for cfe in frame.core_frame_elements:
                filter.add_frame_element(self.object_filters[cfe], cfe)
            self.frame_filters[frame.name] = filter
            rospy.loginfo("{} filter initialized".format(frame.name))
        for frame in self.kb:
            for precondition in frame.preconditions:
                print("Adding {} for {}".format(precondition, frame.name))
                self.frame_filters[frame.name].add_precondition(self.frame_filters[precondition], precondition)
        for _, filter in self.frame_filters.items():
            print(filter.label)
            for name, fe_filter in filter.frame_element_filters.items():
                print("\tcfe: {}, filter: {}".format(name, fe_filter.label))
            try:
                for name, p_filter in filter.precondition_filters.items():
                    print("\tpcond: {}, filter: {}".format(name, p_filter.label))
            except AttributeError:
                print("No preconditions!")
    
    def update_filters(self):
        # if self.update:
        for _, filter in self.object_filters.items():
            filter.update_filter()
            filter.publish()
        for _, filter in self.frame_filters.items():
            filter.update_filter(self.state)
            filter.publish()
            # if filter.label == 'grasp_bottle':
            #     means, covs, weights = filter.bgmm()
            #     print("means")
            #     for cov, weight in zip(covs,weights):
            #         print('\t{}'.format(cov))
            #         print('\t\t{}'.format(weight))
    
    def execute_frame(self, frame_name):
        if frame_name.data == 'grasp_bottle':
            means, covs , weights = self.frame_filters['grasp_bottle'].bgmm()
        elif frame_name.data == 'grasp_spoon':
            means, covs , weights = self.frame_filters['grasp_spoon'].bgmm()
        elif frame_name.data == 'stir_bowl':
            means, covs , weights = self.frame_filters['stir_bowl'].bgmm()
        for m, c, w in zip(means, covs, weights):
            if w > float(1/len(weights)):
                print("Weight: {}".format(w))
                print("Mean: ({:.2f}, {:.2f}, {:.2f})".format(m[0],m[1],m[2]))
                print("Cov diag: ({:.2f}, {:.2f}, {:.2f})".format(c[0,0], c[1,1], c[2,2]))
        print("############################################")
        # if frame_name.data == 'grasp_bottle':
        #     rospy.loginfo("Got request to grasp_bottle")
        #     self.ac.pick()
        # elif frame_name.data == 'pour_bottle':
        #     rospy.loginfo("POUR BOTTLE")
        # else:
        #     rospy.logwarn("INVALID action")

        # mean, _ = self.frame_filters['call_elevator'].bgmm()
        # bmean, _ = self.object_filters['elevator_button'].bgmm()
        # rospy.loginfo('button mean: {}'.format(bmean))
        # rospy.loginfo('action mean: {}'.format(mean))
        # # rospy.loginfo("Going to elevator")
        # # mean, _ = self.frame_filters['go_elevator'].bgmm()
        # # nav_goal_x = mean[0]
        # # nav_goal_y = mean[1]
        # # nav_goal_t = 3.1415192
        # # self.ac.go_to(nav_goal_x, nav_goal_y, nav_goal_t)
        # # rospy.loginfo("SFM: Got request to grasp_bottle")
        # # self.update = False # Stop constant update while executing
        # # mean, _ = self.frame_filters['grasp_bottle'].bgmm()
        # # nav_goal_x = mean[0] - 0.7
        # # nav_goal_y = mean[1] - 0.3
        # # nav_goal_t = 0.0
        # # rospy.loginfo("SFM: Navigating to ({:.4f}, {:.4f}, {:.4f})".format(nav_goal_x, nav_goal_y, nav_goal_t))
        # # self.ac.go_to(nav_goal_x, nav_goal_y, nav_goal_t)
        # # rospy.loginfo("SFM: Raising toros to 0.3")
        # # self.ac.move_torso(0.3)
        # # rospy.loginfo("SFM: Pointing head to (-1.5, -0.7, 0.6)")
        # # self.ac.point_head(-1.5, -0.8, 0.6)
        # p = Pose()
        # p.position.x = mean[0]
        # p.position.y = mean[1]
        # p.position.z = mean[2]
        # p.orientation.w = 1
        # rospy.loginfo("SFM: Send pick command w goal pose: {}".format(p))
        # self.ac.pick(p)
        # rospy.loginfo("SFM: Done")
        # self.update = True

        

if __name__ == '__main__':
    rospy.init_node('sematic_frame_mapping_node')
    foo = SFMClient()
    r = rospy.Rate(20)
    # i = 0
    while not rospy.is_shutdown():
        # rospy.loginfo("Updating...")
        foo.update_filters()
        # print(foo.state.action_history)
        # rospy.loginfo(i)
        # if i == 10:
        #     foo.frame_filters['grasp_bottle'].bgmm()
        # i+=1
        r.sleep()
