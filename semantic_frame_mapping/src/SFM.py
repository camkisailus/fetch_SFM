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
# REGIONS = {
#     'table1': (-2.2, -1.2, -1.25, -0.5, 0.0, 1.5),#(-2.2, -1.2, -1.25, -0.5, 0.6, 0.8),
#     'table2': (-5.75, -4.75, -2.25, -1.5, 0.0, 1.5),#(-5.75, -4.75, -2.25, -1.5, 0.6, 0.8),
#     'neg1': (-5.75, -4.75, -2.25, -1.5, 0, 1.5),
#     'elevator': (-1.2, -1.2, -18.5, -18.5, 0.0, 1.5),#(-1.2, -1.2, -18.5, -18.5, 1, 1),
#     # AWS HOUSE STUFF
    
# }
## AWS HOUSE
REGIONS = {
    'dining_room': (4.5, 8.5, 0.5, 3.5, 0, 1.5),
    'kitchen': (6.5, 9.0, -5, 0, 0, 1.5),
    'bedroom': (-9.0, -3.0, -1.0, 2.4, 0, 1.5)
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
        # rospy.logwarn(self.name)
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.min_z = min_z
        self.max_z = max_z
        # rospy.logwarn(self.min_x, self.min_y, self.min_z, self.max_x, self.max_y, self.max_z)
        self.pub = rospy.Publisher("/region/{}".format(name), Marker, queue_size=1)
        self.marker = Marker()
        self.marker.id = 0
        self.marker.header.frame_id = 'map'
        if self.name == 'table1':
            self.marker.color.r = 1
        elif self.name == 'table2':
            self.marker.color.b = 1
        
        self.marker.color.a = 0.5
        self.marker.type = Marker.CUBE
        self.marker.action = Marker.ADD
        self.marker.lifetime = rospy.Duration(0)
        self.marker.pose.position.x = (min_x + max_x)/2
        self.marker.pose.position.y = (min_y + max_y)/2
        self.marker.pose.position.z = (min_z + max_z)/2
        self.marker.pose.orientation.w = 1.0
        self.marker.scale.x = max_x - min_x
        self.marker.scale.y = max_y - min_y
        self.marker.scale.z = max_z - min_z
        # rospy.logwarn(self.name)
        # rospy.logwarn(self.marker)
        self.pub.publish(self.marker)
    def publish(self):

        self.pub.publish(self.marker)        
    
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
    def __init__(self, experiment_config=None):
        self.regions = {}
        for region in experiment_config['regions']:
            self.regions[region['name']] = Region(region['name'], float(region['min_x']), float(region['max_x']), float(region['min_y']), float(region['max_y']), float(region['min_z']), float(region['max_z']))
        self.object_filters = {}
        for object in experiment_config['objects']:
            name = object['name']
            priors = {}
            for prior in object['priors']:
                priors[self.regions[prior['name']]] = float(prior['weight'])
            self.object_filters[object['name']] = ObjectParticleFilter(100, valid_regions=priors, label=name)
        try:
            for observation in experiment_config['observations']:
                self.object_filters[observation['name']].add_observation_from_config(observation['x'], observation['y'], observation['z'])
        except KeyError as e:
            # no observations in the experiment config... that's fine
            pass

        self.state = State()
        self.frame_filters = {}

        self.kb = init_knowledge_base(rospy.get_param('~sf_dir'), experiment_config['frames'])
        self.execute_frame_sub = rospy.Subscriber("/execute", String, self.execute_frame)
        self.ac = ActionClient()
        for i, frame in enumerate(self.kb):
            valid_regions = None
            filter = FrameParticleFilter(100, frame.name, frame.preconditions, frame.core_frame_elements, valid_regions)
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
            i = 0
            try:
                for _, weight in filter.valid_regions.items():
                    print("\tregion {} weight: {}".format(i, weight))
            except:
                print("No valid regions for : {}".format(filter.label))
                pass
            for name, fe_filter in filter.frame_element_filters.items():
                print("\tcfe: {}, filter: {}".format(name, fe_filter.label))
            try:
                for name, p_filter in filter.precondition_filters.items():
                    print("\tpcond: {}, filter: {}".format(name, p_filter.label))
            except AttributeError:
                print("No preconditions!")

    def publish_regions(self):
        for region in self.regions.values():
            region.publish()


    def update_filters(self, publish=True):
        # if self.update:
        for _, filter in self.object_filters.items():
            filter.update_filter()
            if publish:
                filter.publish()
        for _, filter in self.frame_filters.items():
            filter.update_filter(self.state)
            if publish:
                filter.publish()


    def execute_frame(self, frame_name):
        rospy.logwarn("Got msg to execute {}".format(frame_name))
        if frame_name.data == 'grasp_bottle':
            means, covs , weights = self.frame_filters['grasp_bottle'].bgmm()
        elif frame_name.data == 'grasp_spoon':
            means, covs , weights = self.frame_filters['grasp_spoon'].bgmm()
        elif frame_name.data == 'stir_bowl':
            means, covs , weights = self.frame_filters['stir_bowl'].bgmm()
        max_idx = np.argmax(weights)
        m, c = means[max_idx], covs[max_idx]
        rospy.logwarn("Max Gaussian is centered at ({:.4f}, {:.4f}, {:.4f})".format(m[0], m[1], m[2]))
        # self.ac.go_to(m[0], m[1], 0)
        # for m, c, w in zip(means, covs, weights):
        #     if w > float(1/len(weights)):
        #         print("Weight: {}".format(w))
        #         print("Mean: ({:.2f}, {:.2f}, {:.2f})".format(m[0],m[1],m[2]))
        #         print("Cov diag: ({:.2f}, {:.2f}, {:.2f})".format(c[0,0], c[1,1], c[2,2]))
        # print("############################################")
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
    with open(rospy.get_param("~experiment_config"), 'r') as file:
        experiment_config = yaml.safe_load(file)
    foo = SFMClient(experiment_config)
    rospy.loginfo("SFM Client successfully initialized... Beginning {}".format(experiment_config['title']))
    execute_pub = rospy.Publisher('execute', String, queue_size=10)
    record = rospy.get_param("~record")
    for step in experiment_config['steps']:
        if step == "Update Filters":
            rospy.loginfo("Updating filters")
            for i in range(1000000):
                rospy.logwarn("SFM Driver: Updating Filters Step {}/100".format(i))
                if record:
                    # if we are recording a bag publish every time
                    foo.update_filters(publish=True)
                else:
                    # if not just publish every 10 updates
                    foo.update_filters(publish=(i%10==0))
                foo.publish_regions()
        elif step.startswith('Execute'):
            frame_name = step.split(' ')[-1]
            execute_pub.publish(frame_name)
    rospy.logwarn("Done!")
            

    # r = rospy.Rate(10)
    # i = 0
    # while not rospy.is_shutdown():
    #     print("ITR: {}".format(i+1))
    #     # if i == 100:
    #     #     foo.go_to()
    #     # rospy.loginfo("Updating...")
    #     foo.update_filters()
    #     foo.publish_regions()
    #     # print(foo.state.action_history)
    #     # rospy.loginfo(i)
    #     # if i == 10:
    #     #     foo.frame_filters['grasp_bottle'].bgmm()
    #     i+=1
    #     r.sleep()
