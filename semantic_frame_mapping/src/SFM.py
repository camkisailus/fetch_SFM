#! /usr/bin/python3

import rospy

from particle_filters import *
from utils import *
from std_msgs.msg import Bool
from geometry_msgs.msg import Point, PoseWithCovarianceStamped, Pose
from std_msgs.msg import String
from fetch_actions.msg import MoveBaseRequestAction, MoveBaseRequestGoal, TorsoControlRequestAction, TorsoControlRequestGoal, PointHeadRequestAction, PointHeadRequestGoal, PickRequestAction, PickRequestGoal

class State():
    def __init__(self, action_history):
        self.action_history = action_history
        self.ah_sub = rospy.Subscriber("/add_action_to_action_history", String, self.add_action_to_action_history)
        self.robot_pose_sub = rospy.Subscriber("/amcl_pose", PoseWithCovarianceStamped, self.update_pose)
        self.pose = Pose()
    
    def update_pose(self, pose_msg):
        self.pose = pose_msg.pose.pose
    
    def add_action_to_action_history(self, action_taken):
        try:
            self.action_history.append(action_taken.data)
        except AttributeError:
            self.action_history.append(action_taken)

class Region():
    def __init__(self, name, min_x, max_x, min_y, max_y, min_z, max_z):
        self.name = name
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.min_z = min_z
        self.max_z = max_z
        self.pub = rospy.Publisher("/region/{}".format(name), Marker, queue_size=1)
        self.marker = Marker()
        self.marker.id = 0
        self.marker.header.frame_id = 'map'
        if name.startswith("neg"):
            self.marker.color.r = 1
        
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
        self.pub.publish(self.marker)
    
    def __hash__(self):
        return hash(self.name)

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
        self.cur_pose_sub = rospy.Subscriber("/amcl_pose", PoseWithCovarianceStamped, self.pose_cb)
        self.cur_pose = Pose()

    def pose_cb(self, pose_msg):
        self.cur_pose = pose_msg.pose.pose

    def get_pose(self):
        return self.cur_pose

    def go_to(self, x, y, theta):
        request = MoveBaseRequestGoal()
        request.x = x
        request.y = y
        request.theta = theta
        self.move_base_client.send_goal(request)
        self.move_base_client.wait_for_result()
        return self.move_base_client.get_result()

    def move_torso(self, height):
        request = TorsoControlRequestGoal()
        request.height = height
        self.torso_client.send_goal(request)
        self.torso_client.wait_for_result()
        return self.torso_client.get_result()
    
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
        # Experiment-specific stuff
        self.ac = ActionClient()
        self.neg_regions = set()
        self.regions = {}
        self.experiment_config = experiment_config
        self.record = rospy.get_param("~record")
        self.kb = init_knowledge_base(rospy.get_param('~sf_dir'), experiment_config['frames'])
        self.state = State(experiment_config['action_history'])
        for region in experiment_config['regions']:
            self.regions[region['name']] = Region(region['name'], float(region['min_x']), float(region['max_x']), float(region['min_y']), float(region['max_y']), float(region['min_z']), float(region['max_z']))
        # TODO (kisailus): Give robot ground truth observations at init??
        self.observations = {}
        try:
            for observation in experiment_config['observations']:
                # self.observations[]
                self.object_filters[observation['name']].add_observation_from_config(observation['x'], observation['y'], observation['z'])
        except:
            # no observations in the experiment config... that's fine
            pass

        # Filters
        self.object_filters = {}
        for object in experiment_config['objects']:
            name = object['name']
            priors = {}
            for prior in object['priors']:
                priors[self.regions[prior['name']]] = float(prior['weight'])
            self.object_filters[object['name']] = ObjectParticleFilter(100, valid_regions=priors, label=name)

        self.frame_filters = {}
        for _, frame in enumerate(self.kb):
            filter = FrameParticleFilter(200, frame.name, frame.preconditions, frame.core_frame_elements)
            for cfe in frame.core_frame_elements:
                filter.add_frame_element(self.object_filters[cfe], cfe)
            self.frame_filters[frame.name] = filter
            rospy.loginfo("{} filter initialized".format(frame.name))
        for frame in self.kb:
            for precondition in frame.preconditions:
                print("Adding {} for {}".format(precondition, frame.name))
                self.frame_filters[frame.name].add_precondition(self.frame_filters[precondition], precondition)

        # ROS subscribers
        self.start_exp_sub = rospy.Subscriber("/start_experiment", String, self.run)
        self.execute_frame_sub = rospy.Subscriber("/execute", String, self.execute_frame)
        


        # Debug info for frames
        # for _, filter in self.frame_filters.items():
        #     print(filter.label)
        #     i = 0
        #     try:
        #         for _, weight in filter.valid_regions.items():
        #             print("\tregion {} weight: {}".format(i, weight))
        #     except:
        #         print("No valid regions for : {}".format(filter.label))
        #         pass
        #     for name, fe_filter in filter.frame_element_filters.items():
        #         print("\tcfe: {}, filter: {}".format(name, fe_filter.label))
        #     try:
        #         for name, p_filter in filter.precondition_filters.items():
        #             print("\tpcond: {}, filter: {}".format(name, p_filter.label))
        #     except AttributeError:
        #         print("No preconditions!")
        

    def publish_regions(self):
        for region in self.regions.values():
            region.publish()
        for region in self.neg_regions:
            region.publish()


    def update_filters(self, publish=True):
        for _, filter in self.object_filters.items():
            filter.update_filter()
            if publish:
                filter.publish()
        for _, filter in self.frame_filters.items():
            filter.update_filter(self.state)
            if publish:
                filter.publish()
    
    def add_observations(self, possible_observations=[]):
        # add observations if they are within 5m of the robot's current pose, else add negative region
        cur_pose = self.state.pose
        for _, filter in self.object_filters.items():
            added = False
            for observation in possible_observations:
                x_dist = (observation['x'] - cur_pose.position.x)**2
                y_dist = (observation['y'] - cur_pose.position.y)**2
                if np.sqrt(x_dist + y_dist) <= 5.0:
                    filter.add_observation_from_config(observation['x'], observation['y'], observation['z'])
                    added = True
            if not added:
                min_x = cur_pose.position.x - 2
                max_x = cur_pose.position.x + 2
                min_y = cur_pose.position.y - 2
                max_y = cur_pose.position.y + 2
                min_z = 0
                max_z = 1.5
                reg = Region("{}_neg_reg_{}".format(filter.label, len(self.neg_regions)), min_x, max_x, min_y, max_y, min_z, max_z)
                filter.add_negative_region(reg)
                self.neg_regions.add(reg)

    def run_observation_routine(self, frame=None):
        """
        This is a simulated object detection method
         
        If the robot in near or in a region that an object is in, we add the observation
        else, add that region as a negative obersvation region for that object
        
        """
        cur_pose = self.state.pose
        min_x = cur_pose.position.x - 2
        max_x = cur_pose.position.x + 2
        min_y = cur_pose.position.y - 2
        max_y = cur_pose.position.y + 2
        min_z = 0
        max_z = 2.0
        reg = Region("neg_reg_{}".format(len(self.neg_regions)), min_x, max_x, min_y, max_y, min_z, max_z)
        region_added = False
        pos_added = []
        for _, filter in self.object_filters.items():
            try:
                for obs in self.experiment_config['observations']:
                    rospy.logwarn("{} location is ({}, {})".format(obs['name'], obs['x'], obs['y']))
                    # if obs['name'] != filter.label:
                    #     continue
                    x_err =  (obs['x'] - self.state.pose.position.x)**2
                    y_err = (obs['y'] - self.state.pose.position.y)**2
                    if np.sqrt(x_err + y_err ) <= 1 and obs['name'] == filter.label:
                        if frame == 'grasp_spoon' and filter.label == 'spoon':
                        # simulate completed action
                            rospy.logwarn("Successfully completed {}".format(frame))
                            return True
                        elif frame == 'stir_cup' and filter.label == 'cup':
                            rospy.logwarn("Successfully completed {}".format(frame))
                            return True
                        elif frame == 'grasp_cup' and filter.label == 'cup':
                            rospy.logwarn("Adding observation to {} dist to obj is {}".format(filter.label, np.sqrt(x_err+y_err)))
                            filter.add_observation_from_config(obs['x'], obs['y'], obs['z'])
                            pos_added.append(filter.label)
                            # rospy.logwarn("Successfully completed {}".format(frame))
                            # return True
                    elif np.sqrt(x_err + y_err) < 5 and obs['name'] == filter.label:
                        rospy.logwarn("Adding observation to {} dist to obj is {}".format(filter.label, np.sqrt(x_err+y_err)))
                        filter.add_observation_from_config(obs['x'], obs['y'], obs['z'])
                        pos_added.append(filter.label)

            except KeyError:
                # no observations defined in the experiment
                pass
        for _, filter in self.object_filters.items():
            if filter.label not in pos_added:
                rospy.logwarn("Adding neg region to {}".format(filter.label))
                filter.add_negative_region(reg)
                self.neg_regions.add(reg)
        return False




    def execute_frame(self, frame_name):
        rospy.logwarn("Got msg to execute {}".format(frame_name))
        preconditions = []
        if self.frame_filters[frame_name].preconditions is not None:
            preconditions = self.frame_filters[frame_name].preconditions
        else:
            preconditions = []
            cur_action = frame_name
        rospy.logwarn("{} has preconditions: {}".format(frame_name, preconditions))
        for frame in preconditions:
            if frame in self.state.action_history:
                # pop action off preconditions since it's completed
                preconditions = preconditions[1:]
            else:
                cur_action = frame
        rospy.logwarn("Cur action is : {}".format(cur_action))
        
        # preconditions = self.frame_filters[frame_name].preconditions
        for precondition in preconditions:
            chances = 3
            precondition_complete = False
            while chances > 0 and not precondition_complete:
                rospy.logwarn("Updating filters with {} chance(s) remaining".format(chances))
                # update filters
                update_steps = 50
                for i in range(update_steps):
                    # rospy.logwarn("SFM Driver: Updating Filters Step {}/{}".format(i, update_steps))
                    if self.record:
                        # if we are recording a bag publish every time
                        self.update_filters(publish=True)
                    else:
                        # if not just publish every 10 updates
                        self.update_filters(publish=(i%10==0))
                # go to max
                means, covs, weights = self.frame_filters[frame_name].bgmm()
                max_idx = np.argmax(weights)
                max_weight_mean = means[max_idx]
                self.ac.go_to(max_weight_mean[0], max_weight_mean[1], 0)
                precondition_complete = self.run_observation_routine(precondition)
                if precondition_complete:
                    self.state.add_action_to_action_history(precondition)
                chances-=1
            if not precondition_complete:
                # out of chances and unable to complete some precondition
                return False
        rospy.logwarn("Finished all preconditions!")
        # finished all preconditions try to do final action
        chances = 3
        while chances > 0:
            rospy.logwarn("Updating filters with {} chance(s) remaining".format(chances))
            # update filters
            update_steps = 50
            for i in range(update_steps):
                # rospy.logwarn("SFM Driver: Updating Filters Step {}/{}".format(i, update_steps))
                if self.record:
                    # if we are recording a bag publish every time
                    self.update_filters(publish=True)
                else:
                    # if not just publish every 10 updates
                    self.update_filters(publish=(i%10==0))
            # go to max
            means, covs, weights = self.frame_filters[frame_name].bgmm()
            max_idx = np.argmax(weights)
            max_weight_mean = means[max_idx]
            self.ac.go_to(max_weight_mean[0], max_weight_mean[1], 0)
            task_complete = self.run_observation_routine(frame_name)
            if task_complete:
                return True
            chances-=1
        return False

        
            
    
    def run(self, data):
        for step in self.experiment_config['steps']:
            if step == "Update Filters":
                rospy.loginfo("Updating filters")
                update_steps = 30
                for i in range(update_steps):
                    # rospy.logwarn("SFM Driver: Updating Filters Step {}/{}".format(i, update_steps))
                    if self.record:
                        # if we are recording a bag publish every time
                        foo.update_filters(publish=True)
                    else:
                        # if not just publish every 10 updates
                        foo.update_filters(publish=(i%10==0))
                    foo.publish_regions()
            elif step.startswith('Execute'):
                frame_name = step.split(' ')[-1]
                if foo.execute_frame(frame_name):
                    rospy.logwarn("SFM Driver: Execution Success")
                else:
                    rospy.logwarn("SFM Driver: Execution Failure")
            elif step == "Observe":
                try:
                    foo.add_observations(experiment_config['observations'])
                except KeyError:
                    foo.add_observations()
        rospy.logwarn("Done!")

        

if __name__ == '__main__':
    rospy.init_node('sematic_frame_mapping_node')
    with open(rospy.get_param("~experiment_config"), 'r') as file:
        experiment_config = yaml.safe_load(file)
    foo = SFMClient(experiment_config)
    rospy.loginfo("SFM Client successfully initialized... Beginning {}".format(experiment_config['title']))
    
    
    r = rospy.Rate(10)
    i = 0
    while not rospy.is_shutdown():
        # if i < 20:
        #     print("ITR: {}".format(i+1))
        #     # if i == 100:
        #     #     foo.go_to()
        #     # rospy.loginfo("Updating...")
        foo.update_filters()
        #     foo.publish_regions()
        #     # print(foo.state.action_history)
        #     # rospy.loginfo(i)
        #     # if i == 10:
        #     #     foo.frame_filters['grasp_bottle'].bgmm()
        #     i+=1
        r.sleep()
