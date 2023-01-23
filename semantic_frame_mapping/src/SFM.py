#! /usr/bin/python3

import rospy

from executor import Executor

from particle_filters import *
from utils import *
from std_msgs.msg import Bool
from geometry_msgs.msg import Point, PoseWithCovarianceStamped, Pose, PoseStamped, Quaternion
from std_msgs.msg import String, Int8
from nav_msgs.srv import GetPlan, GetPlanResponse
from grasploc_wrapper_msgs.msg import GrasplocRequestAction, GrasplocRequestGoal
from gazebo_msgs.srv import SetModelState, SetModelStateResponse
from gazebo_msgs.srv import SpawnModel, SpawnModelResponse
from gazebo_msgs.msg import ModelState      


class SFMClient(Executor):
    def __init__(self, experiment_config=None):
        super().__init__(experiment_config)
        # Experiment-specific stuff
        self.update = True
        self.neg_regions = set()
        self.regions = {}
        self.record = rospy.get_param("~record")
        self.kb = init_knowledge_base(rospy.get_param('~sf_dir'), self.experiment_config['frames'])
        for region in self.experiment_config['regions']:
            self.regions[region['name']] = Region(region['name'], float(region['min_x']), float(region['max_x']), float(region['min_y']), float(region['max_y']), float(region['min_z']), float(region['max_z']))
        # TODO (kisailus): Give robot ground truth observations at init??
        self.observations = {}
        try:
            for observation in self.experiment_config['observations']:
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
            self.object_filters[object['name']].publish()

        self.frame_filters = {}
        for _, frame in enumerate(self.kb):
            filter = FrameParticleFilter(100, frame.name, frame.preconditions, frame.core_frame_elements)
            filter.publish()
            for cfe in frame.core_frame_elements:
                filter.add_frame_element(self.object_filters[cfe], cfe)
            self.frame_filters[frame.name] = filter
            rospy.loginfo("{} filter initialized".format(frame.name))
        for frame in self.kb:
            for precondition in frame.preconditions:
                print("Adding {} for {}".format(precondition, frame.name))
                self.frame_filters[frame.name].add_precondition(self.frame_filters[precondition], precondition)
        rospy.logwarn("SFM INIT DONE")
        # ROS subscribers
        self.start_exp_sub = rospy.Subscriber("/start_experiment", String, self.run)
        self.execute_frame_sub = rospy.Subscriber("/execute", String, self.execute_frame)
        # self.update_filters_sub = rospy.Subscriber("/update_filters", Int8, self.update_filters)
        


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
        
    # def update_filters(self, msg):
    #     rospy.logwarn("Updating Filters")
    #     for _ in range(msg.data*10):
    #         self.update_filters()
    #     rospy.logwarn("Done updating filters")
        
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

    def run_observation_routine(self):
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
                    # rospy.logwarn("{} location is ({}, {})".format(obs['name'], obs['x'], obs['y']))
                    # if obs['name'] != filter.label:
                    #     continue
                    x_err =  (obs['x'] - self.state.pose.position.x)**2
                    y_err = (obs['y'] - self.state.pose.position.y)**2
                    # if np.sqrt(x_err + y_err ) <= 1 and obs['name'] == filter.label:
                    #     if frame == 'grasp_spoon' and filter.label == 'spoon':
                    #     # simulate completed action
                    #         rospy.logwarn("Successfully completed {}".format(frame))
                    #         return True
                    #     elif frame == 'stir_cup' and filter.label == 'cup':
                    #         rospy.logwarn("Successfully completed {}".format(frame))
                    #         return True
                    #     elif frame == 'grasp_cup' and filter.label == 'cup':
                    #         rospy.logwarn("Adding observation to {} dist to obj is {}".format(filter.label, np.sqrt(x_err+y_err)))
                    #         filter.add_observation_from_config(obs['x'], obs['y'], obs['z'])
                    #         pos_added.append(filter.label)
                    #         # rospy.logwarn("Successfully completed {}".format(frame))
                    #         # return True
                    if np.sqrt(x_err + y_err) < 5 and obs['name'] == filter.label:
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

    def dist(self, robot, obj):
        x_dist = np.abs(robot.position.x - obj.x)
        y_dist = np.abs(robot.position.y - obj.y)
        # z_dist = np.abs(robot.position.z - obj.z)
        return np.sqrt(x_dist**2 + y_dist**2)

    def execute_frame(self, frame_name):
        self.update = False
        if frame_name.data == 'make_coffee':
            best_particle = self.frame_filters[frame_name.data].particles[np.argmax(self.frame_filters[frame_name.data].weights)]
            self.ac.move_torso(0.4)
            self.ac.point_head(best_particle[0], best_particle[1], best_particle[2]-0.1)
            p = Pose()
            p.position.x = best_particle[0]
            p.position.y = best_particle[1]
            p.position.z = best_particle[2]
            suc = self.ac.pick(mode=0, goal=p) # pick master_chef_can
            if suc:
                self.state.add_action_to_action_history('grasp_master_chef_can')
                for _ in range(1000):
                    self.update_filters(publish=True)
                best_particle = self.frame_filters[frame_name.data].particles[np.argmax(self.frame_filters[frame_name.data].weights)]
                self.ac.point_head(best_particle[0], best_particle[1], best_particle[2]-0.1)
                p = Pose()
                p.position.x = best_particle[0]
                p.position.y = best_particle[1]-0.15
                p.position.z = best_particle[2]
                self.ac.pick(mode=2, goal=p) # place since we cannot pour yet


        else:
            # Get best particle
            best_particle = self.frame_filters[frame_name.data].particles[np.argmax(self.frame_filters[frame_name.data].weights)]
            rospy.logwarn("[SFM DRIVER]: Highest weighted grasp_block particle at ({}, {}, {})".format(best_particle[0], best_particle[1], best_particle[2]))
            # Nav to best particle
            # self.ac.go_to(best_particle[0], best_particle[1], 0.0)
            self.ac.move_torso(0.4)
            self.ac.point_head(best_particle[0], best_particle[1], best_particle[2]-0.1)
            # p = PoseStamped()
            # p.header.frame_id = 'map'
            # p.pose.position.x = best_particle[0]
            # p.pose.position.y = best_particle[1]
            # p.pose.position.z = best_particle[2]
            # p.pose.orientation.w = 1.0
            p = Pose()
            p.position.x = best_particle[0]
            p.position.y = best_particle[1]
            p.position.z = best_particle[2]
            p.orientation.w = 1
            
            suc = self.ac.pick(mode=0, goal=p)
            # rospy.logwarn(suc)
            # rospy.sleep(10)
            # self.ac.pick(mode=2)
            # rospy.sleep(10)
            # self.ac.pick(mode=1)
        self.update = True
            # Run observation routine
            # Update filters

        # if frame_name.data == 'grasp_master_chef_can':
        #     rospy.logwarn("Got request to grasp master can")
        #     rospy.logwarn("First going to look at the can")
        #     # frame_bgmm = self.frame_filters['grasp_master_chef_can'].bgmm()
        #     grasp_mcc = self.frame_filters[frame_name.data]
        #     mcc_obj = grasp_mcc.frame_element_filters['master_chef_can']
        #     mcc_det = mcc_obj.observations[0]
        #     # pick_pose = Pose()
        #     # pick_pose.position.x = mcc_det.x
        #     # pick_pose.position.y = mcc_det.y + 0.02
        #     # pick_pose.position.z = mcc_det.z
        #     # rospy.logwarn("Sending pick location to picker")
        #     # self.ac.pick(mode=1, goal=pick_pose)
            
        #     # means, covs, weights = self.frame_filters[frame_name.data].bgmm()
        #     # max_idx = np.argmax(weights)
        #     # max_weight_mean = means[max_idx]
        #     rospy.logwarn("Pointing head to: ({}, {}, {})".format(mcc_det.x, mcc_det.y, mcc_det.z))
        #     self.ac.point_head(mcc_det.x, mcc_det.y, mcc_det.z)
        #     dist = self.dist(self.state.pose, mcc_det)
        #     rospy.logwarn("Object is {} m away from the robot")
        #     if dist > 0.8:
        #         rospy.logwarn("Now navigate toward the obj")
        #         nav_goal_x = mcc_det.x
        #         nav_goal_y = mcc_det.y + 0.6
        #         nav_goal_t = -np.pi/2  #np.arctan2(mcc_det.x, mcc_det.y)
        #         rospy.logwarn("Nav goal: ({}, {}, {})".format(nav_goal_x, nav_goal_y, nav_goal_t))
        #         self.ac.go_to(nav_goal_x, nav_goal_y, nav_goal_t)
        #     self.ac.point_head(mcc_det.x, mcc_det.y, mcc_det.z)
        #     pick_pose = Pose()
        #     pick_pose.position.x = mcc_det.x
        #     pick_pose.position.y = mcc_det.y + 0.02
        #     pick_pose.position.z = mcc_det.z
        #     rospy.logwarn("Sending pick location to picker")
        #     self.ac.pick(mode=1, goal=pick_pose)
            
# def pick(self, mode=0, goal=None):
#     if mode == 1:
#         assert(goal is not None)
#         request.goal = goal
#     request = PickRequestGoal()
#     request.mode = mode
#     self.pick_client.send_goal(request)
#     rospy.loginfo("Sent pick_client goal")
#     self.pick_client.wait_for_result()

    # def execute_frame(self, frame_name):
    #     rospy.logwarn("Got msg to execute {}".format(frame_name))
    #     preconditions = []
    #     if self.frame_filters[frame_name].preconditions is not None:
    #         preconditions = self.frame_filters[frame_name].preconditions
    #     else:
    #         preconditions = []
    #         cur_action = frame_name
    #     rospy.logwarn("{} has preconditions: {}".format(frame_name, preconditions))
    #     for frame in preconditions:
    #         if frame in self.state.action_history:
    #             # pop action off preconditions since it's completed
    #             preconditions = preconditions[1:]
    #         else:
    #             cur_action = frame
    #     rospy.logwarn("Cur action is : {}".format(cur_action))
        
    #     # preconditions = self.frame_filters[frame_name].preconditions
    #     for precondition in preconditions:
    #         chances = 3
    #         precondition_complete = False
    #         while chances > 0 and not precondition_complete:
    #             rospy.logwarn("Updating filters with {} chance(s) remaining".format(chances))
    #             # update filters
    #             update_steps = 50
    #             for i in range(update_steps):
    #                 # rospy.logwarn("SFM Driver: Updating Filters Step {}/{}".format(i, update_steps))
    #                 if self.record:
    #                     # if we are recording a bag publish every time
    #                     self.update_filters(publish=True)
    #                 else:
    #                     # if not just publish every 10 updates
    #                     self.update_filters(publish=(i%10==0))
    #             # go to max
    #             means, covs, weights = self.frame_filters[frame_name].bgmm()
    #             max_idx = np.argmax(weights)
    #             max_weight_mean = means[max_idx]
    #             self.ac.go_to(max_weight_mean[0], max_weight_mean[1], 0)
    #             precondition_complete = self.run_observation_routine(precondition)
    #             if precondition_complete:
    #                 self.state.add_action_to_action_history(precondition)
    #             chances-=1
    #         if not precondition_complete:
    #             # out of chances and unable to complete some precondition
    #             return False
    #     rospy.logwarn("Finished all preconditions!")
    #     # finished all preconditions try to do final action
    #     chances = 3
    #     while chances > 0:
    #         rospy.logwarn("Updating filters with {} chance(s) remaining".format(chances))
    #         # update filters
    #         update_steps = 50
    #         for i in range(update_steps):
    #             # rospy.logwarn("SFM Driver: Updating Filters Step {}/{}".format(i, update_steps))
    #             if self.record:
    #                 # if we are recording a bag publish every time
    #                 self.update_filters(publish=True)
    #             else:
    #                 # if not just publish every 10 updates
    #                 self.update_filters(publish=(i%10==0))
    #         # go to max
    #         means, covs, weights = self.frame_filters[frame_name].bgmm()
    #         max_idx = np.argmax(weights)
    #         max_weight_mean = means[max_idx]
    #         self.ac.go_to(max_weight_mean[0], max_weight_mean[1], 0)
    #         task_complete = self.run_observation_routine(frame_name)
    #         if task_complete:
    #             return True
    #         chances-=1
    #     return False

        
            
    
    def run(self):
        # rospy.wait_for_service("/gazebo/spawn_sdf_model")
        # spawn_model_client = rospy.ServiceProxy('/gazebo/spawn_sdf_model', SpawnModel)
        # for object in self.experiment_config['objects']:
        #     roll = object['gt_loc']['roll']
        #     pitch = object['gt_loc']['pitch']
        #     yaw = object['gt_loc']['yaw']
        #     spawn_model_client(
        #         model_name='ground_plane',
        #         model_xml=open('/home/cuhsailus/Desktop/Research/22_academic_year/gazebo_ws/src/gazebo_ycb/models/{}/model.sdf'.format(object['name']), 'r').read(),
        #         robot_namespace='/foo',
        #         initial_pose=Pose(
        #             position=Point(
        #                 object['gt_loc']['x'], 
        #                 object['gt_loc']['y'], 
        #                 object['gt_loc']['z']), 
        #             orientation=Quaternion(
        #                 np.sin(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) - np.cos(roll/2) * np.sin(pitch/2) * np.sin(yaw/2),
        #                 np.cos(roll/2) * np.sin(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.cos(pitch/2) * np.sin(yaw/2),
        #                 np.cos(roll/2) * np.cos(pitch/2) * np.sin(yaw/2) - np.sin(roll/2) * np.sin(pitch/2) * np.cos(yaw/2),
        #                 np.cos(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)
        #                 )),
        #         reference_frame='world'
        #     )
        # spawn_model_srv = rospy.ServiceProxy("/gazebo/spawn_urdf_model", SpawnModel)
        # root = 
        # for object in self.experiment_config['objects']:

        #     msg = SpawnModel()
        #     msg.model_name = object['name']
        #     msg.model_xlm = os.path.join()
        # gcb_filter = self.frame_filters['grasp_cracker_box']
        # rospy.wait_for_service("/gazebo/set_model_state")
        # set_state = rospy.ServiceProxy("/gazebo/set_model_state", SetModelState)
        # for object in self.experiment_config['objects']:
        #     msg = ModelState()
        #     msg.model_name = object['name']
        #     msg.pose.position.x = object['gt_loc']['x']
        #     msg.pose.position.y = object['gt_loc']['y']
        #     msg.pose.position.z = object['gt_loc']['z']
            # roll = object['gt_loc']['roll']
            # pitch = object['gt_loc']['pitch']
            # yaw = object['gt_loc']['yaw']
            # msg.pose.orientation.x = np.sin(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) - np.cos(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)
            # msg.pose.orientation.y = np.cos(roll/2) * np.sin(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.cos(pitch/2) * np.sin(yaw/2)
            # msg.pose.orientation.z = np.cos(roll/2) * np.cos(pitch/2) * np.sin(yaw/2) - np.sin(roll/2) * np.sin(pitch/2) * np.cos(yaw/2)
            # msg.pose.orientation.w = np.cos(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)
        #     set_state(msg)
        # for i in range(21):
        #     if i % 10 == 0:
        #         rospy.logwarn(i)
        #     self.update_filters(publish=True)
        # highest_weighted_particle = gcb_filter.particles[np.argmax(gcb_filter.weights)]
        # rospy.logwarn("Highest weighted particle located at ({:.4f}, {:.4f}, {:.4f}".format(highest_weighted_particle[0], highest_weighted_particle[1], highest_weighted_particle[2]))
        # self.ac.go_to(highest_weighted_particle[0], highest_weighted_particle[1], 0)
        # self.ac.point_head(highest_weighted_particle[0], highest_weighted_particle[1], highest_weighted_particle[2])
        # self.run_observation_routine()
        # for i in range(21):
        #     if i % 10 == 0:
        #         rospy.logwarn(i)
        #     self.update_filters(publish=True)
        # highest_weighted_particle = gcb_filter.particles[np.argmax(gcb_filter.weights)]
        # rospy.logwarn("Highest weighted particle located at ({:.4f}, {:.4f}, {:.4f}".format(highest_weighted_particle[0], highest_weighted_particle[1], highest_weighted_particle[2]))
        # self.ac.go_to(highest_weighted_particle[0], highest_weighted_particle[1], 0)
        # self.ac.point_head(highest_weighted_particle[0], highest_weighted_particle[1], highest_weighted_particle[2])
        # self.run_observation_routine()
        # run yolo wait for detections
        
        

        # rospy.logwarn("Set all model states")
        # rospy.loginfo("Moving to kitchen counter...")
        # self.ac.go_to(6,0,0)
        # self.ac.go_to(6.8, -3.3, -1.57079632679)
        # self.ac.go_to(6.8, -5.3, -1.57079632679)
        # rospy.loginfo("Raising torso...")
        # self.ac.move_torso(0.4)
        # rospy.loginfo("Looking at (6.8, -6, 0.8)")
        # self.ac.point_head(6.8, -6, 0.6)
        # self.ac.pick(mode=0) # mode == 0 --> pick
        # self.ac.pick(mode=2) # mode == 2 --> place
        # self.ac.pick(mode=1) # mode == 1 --> tuck_arm
        # self.ac.move_torso(0.0)
        
        while not rospy.is_shutdown():
            if self.update:
                self.update_filters(publish=True)
                self.publish_regions()
            else:
                pass

        # for step in self.experiment_config['steps']:
        #     if step == "Update Filters":
        #         rospy.loginfo("Updating filters")
        #         update_steps = 30
        #         for i in range(update_steps):
        #             # rospy.logwarn("SFM Driver: Updating Filters Step {}/{}".format(i, update_steps))
        #             if self.record:
        #                 # if we are recording a bag publish every time
        #                 foo.update_filters(publish=True)
        #             else:
        #                 # if not just publish every 10 updates
        #                 foo.update_filters(publish=(i%10==0))
        #             foo.publish_regions()
        #     elif step.startswith('Execute'):
        #         frame_name = step.split(' ')[-1]
        #         if foo.execute_frame(frame_name):
        #             rospy.logwarn("SFM Driver: Execution Success")
        #         else:
        #             rospy.logwarn("SFM Driver: Execution Failure")
        #     elif step == "Observe":
        #         try:
        #             foo.add_observations(experiment_config['observations'])
        #         except KeyError:
        #             foo.add_observations()
        # rospy.logwarn("Done!")

        

if __name__ == '__main__':
    rospy.init_node('sematic_frame_mapping_node')

    with open(rospy.get_param("~experiment_config"), 'r') as file:
        experiment_config = yaml.safe_load(file)
    foo = SFMClient(experiment_config)
    rospy.loginfo("SFM Client successfully initialized... Beginning {}".format(experiment_config['title']))
    foo.run()
