#! /usr/bin/python3

import rospy

from particle_filters import *
from utils import *
from std_msgs.msg import Bool
from geometry_msgs.msg import Point, PoseWithCovarianceStamped, Pose, PoseStamped, Quaternion
from std_msgs.msg import String, Int8
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from fetch_actions.msg import MoveBaseRequestAction, MoveBaseRequestGoal, TorsoControlRequestAction, TorsoControlRequestGoal, PointHeadRequestAction, PointHeadRequestGoal, PickRequestAction, PickRequestGoal
from nav_msgs.srv import GetPlan, GetPlanResponse
from grasploc_wrapper_msgs.msg import GrasplocRequestAction, GrasplocRequestGoal
from gazebo_msgs.srv import SetModelState, SetModelStateResponse
from gazebo_msgs.srv import SpawnModel, SpawnModelResponse
from gazebo_msgs.msg import ModelState
import tf
from actionlib_msgs.msg import GoalID
from perception.msg import YOLORequestAction, YOLORequestGoal, YOLORequestResult

class State():
    '''
        State class tracks the pose of the robot, current grasped object, and a history of completed actions.
        For now, we also pre-define some keyposes for easier navigation/manipulation.
    '''
    def __init__(self, action_history):
        self.action_history = action_history
        self.ah_sub = rospy.Subscriber(
            "/add_action_to_action_history", String, self.add_action_to_action_history)
        self.robot_pose_sub = rospy.Subscriber(
            "/amcl_pose", PoseWithCovarianceStamped, self.update_pose)
        self.pose = Pose()
        self.grasped_object = None
        
        # Predefined keyposes
        self.lab_table_1 = PoseStamped()
        self.lab_table_1.header.frame_id = "map"
        self.lab_table_1.pose.position.x = 0.00525866035576
        self.lab_table_1.pose.position.y = 2.30981243854
        self.lab_table_1.pose.orientation.z = 0.581420008308
        self.lab_table_1.pose.orientation.w = 0.813603572963

        self.lab_table_d = PoseStamped()
        self.lab_table_d.header.frame_id = "map"
        self.lab_table_d.pose.position.x = 0.224
        self.lab_table_d.pose.position.y = 5.864
        self.lab_table_d.pose.orientation.z = 0.742
        self.lab_table_d.pose.orientation.w = 0.670

        self.collab_table_d = PoseStamped()
        self.collab_table_d.header.frame_id = "map"
        self.collab_table_d.pose.position.x = -3.98
        self.collab_table_d.pose.position.y = 16.978
        self.collab_table_d.pose.orientation.z = -0.036
        self.collab_table_d.pose.orientation.w = 0.999
    
        self.keyposes = {'lab_table_d': self.lab_table_d, 'light_table': self.lab_table_1, 'collab_table_d': self.collab_table_d}

    def update_pose(self, pose_msg):
        '''
            Keep track of the pose of the robot by subscribing to the amcl msg
        '''
        self.pose = pose_msg.pose.pose

    def add_action_to_action_history(self, action_taken):
        '''
            Add succesfully compeleted actions to the actions history. This is used in the context potential in SeFM
        '''
        try:
            self.action_history.append(action_taken.data)
            if "grasp" in action_taken.data:
                self.grasped_object = action_taken.data.split("_", 1)[-1] # grasp_cracker_box -> cracker_box
        except AttributeError:
            self.action_history.append(action_taken)

class Region():
    '''
        Regions are 3D cuboids in the map that can be "negative" or "positive" regions.
        Negative regions are regions we've observed but not seen a specific object.
        Positive regions are usually reserved for object-leve priors.
    '''
    def __init__(self, name, min_x, max_x, min_y, max_y, min_z, max_z, cube_in_map=None):
        self.name = name
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.min_z = min_z
        self.max_z = max_z
        
        if cube_in_map is None:
            self.pub = rospy.Publisher("/region/{}".format(name), Marker, queue_size=1)
            self.marker = Marker()
            self.marker.id = 0
            self.marker.header.frame_id = 'map'
            if "neg" in name:
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

        else:
            self.pub = rospy.Publisher("/region/{}".format(name), MarkerArray, queue_size=1)
            frame_id = "/map"
            self.cube = cube_in_map
            self.marker_array = MarkerArray()
            self.marker_array_line_list(cube_in_map, frame_id)
        
    def check_point_in_cube(self, point):
        dir1 = (self.cube[4]-self.cube[0])
        size1 = np.linalg.norm(dir1)
        dir1 = dir1 / size1

        dir2 = (self.cube[3]-self.cube[0])
        size2 = np.linalg.norm(dir2)
        dir2 = dir2 / size2

        dir3 = (self.cube[1]-self.cube[0])
        size3 = np.linalg.norm(dir3)
        dir3 = dir3 / size3

        cube3d_center = (self.cube[0] + self.cube[6])/2.0

        dir_vec = point - cube3d_center
        if ((np.absolute(np.dot(dir_vec, dir1)) * 2) <= size1) and ((np.absolute(np.dot(dir_vec, dir2)) * 2) <= size2) and ((np.absolute(np.dot(dir_vec, dir3)) * 2) <= size3):
            return True
        else :
            return False

    def marker_array_line_list(self, cube_in_map, frame_id):
        for i in range(0,4):
            markerLL = self.marker_line_list(cube_in_map[i], cube_in_map[i+4], frame_id)
            self.marker_array.markers.append(markerLL) #vertical edges

            if i < 3:
                markerLL = self.marker_line_list(cube_in_map[i], cube_in_map[i+1], frame_id)
            else:
                markerLL = self.marker_line_list(cube_in_map[3], cube_in_map[0], frame_id)

            self.marker_array.markers.append(markerLL) #bottom edges

        for i in range(4,8):
            if i < 7:
                markerLL = self.marker_line_list(cube_in_map[i], cube_in_map[i+1], frame_id)
            else:
                markerLL = self.marker_line_list(cube_in_map[7], cube_in_map[4], frame_id)

            self.marker_array.markers.append(markerLL) #top edges

        self.pub.publish(self.marker_array)              


    def marker_line_list(self, point1, point2, frame_id):
        marker = Marker()
        marker.header.frame_id = frame_id
        marker.type = marker.LINE_LIST
        marker.color.a = 1.0
        marker.action = marker.ADD

        #marker scale
        marker.scale.x = 0.1
        marker.scale.y = 0.1
        marker.scale.z = 0.1

        #marker color
        marker.color.a = 1

        #marker orientation
        marker.pose.orientation.x = 0.0
        marker.pose.orientation.y = 0.0
        marker.pose.orientation.z = 0.0
        marker.pose.orientation.w = 1.0

        #marker position
        marker.pose.position.x = 0.0
        marker.pose.position.y = 0.0
        marker.pose.position.z = 0.0

        #marker line points
        marker.points =[]

        #first point
        first_point = Point()
        first_point.x = point1[0]
        first_point.y = point1[1]
        first_point.z = point1[2]
        marker.points.append(first_point)


        #second point
        second_point = Point()
        second_point.x = point2[0]
        second_point.y = point2[1]
        second_point.z = point2[2]
        marker.points.append(second_point)

        # self.pub.publish(self.marker)
        return marker

    def __hash__(self):
        return hash(self.name)

    def publish(self):
        self.pub.publish(self.marker)        
    
    def get_bounds(self):
        return (self.min_x, self.max_x, self.min_y, self.max_y, self.min_z, self.max_z)

class ActionClient():
    '''
        Client side to the action server running on Fetch under the node 'fetch_actions'.
        Through this client we can move_base (navigation), control torso height, point the head, do manipulation tasks, and call our YOLO detector 
    '''
    def __init__(self):
        self.move_base_client = actionlib.SimpleActionClient(
            "kisailus_move_base", MoveBaseRequestAction)
        self.move_base_client.wait_for_server()
        rospy.logwarn("Connected to move_base server")
        self.torso_client = actionlib.SimpleActionClient(
            "kisailus_torso_controller", TorsoControlRequestAction)
        self.torso_client.wait_for_server()
        rospy.logwarn("Connected to torso client")
        self.point_head_client = actionlib.SimpleActionClient(
            "kisailus_point_head", PointHeadRequestAction)
        self.point_head_client.wait_for_server()
        rospy.logwarn("Connected to point head client")
        self.pick_client = actionlib.SimpleActionClient(
            "kisailus_pick", PickRequestAction)
        self.pick_client.wait_for_server()
        rospy.logwarn("Connected to pick server")
        self.cancel_nav_pub = rospy.Publisher("/move_base/cancel", GoalID)
        self.yolo_client = actionlib.SimpleActionClient("yolo_detector", YOLORequestAction)
        # self.pick_sub = rospy.Subscriber("pick", Bool, self.pick_from_cmd)
        # self.tf_listener = tf.TransformListener()
        # self.grasp_pub = rospy.Publisher('request_grasp_pts', Bool, queue_size=10)
        # self.point_head_pub = rospy.Publisher('/point_head/at', Point, queue_size=10)
        # self.cur_pose_sub = rospy.Subscriber("/amcl_pose", PoseWithCovarianceStamped, self.pose_cb)
        # self.cur_pose = Pose()

    def run_yolo(self):
        goal = YOLORequestGoal()
        goal.publish_detections = True
        self.yolo_client.send_goal(goal)
        self.yolo_client.wait_for_result()
        return self.yolo_client.get_result()

    def pose_cb(self, pose_msg):
        self.cur_pose = pose_msg.pose.pose

    def get_pose(self):
        return self.cur_pose

    def cancelNav(self):
        self.cancel_nav_pub.publish(GoalID())

    def goToKeyPose(self, keypose: PoseStamped):
        """
            Special move to a specified keypoint in the map
        """
        move_base_client = actionlib.SimpleActionClient(
            "move_base", MoveBaseAction)
        move_base_client.wait_for_server()
        move_goal = MoveBaseGoal()
        move_goal.target_pose = keypose
        move_goal.target_pose.header.stamp = rospy.Time.now()
        rospy.logwarn("Sending this goal to move_base: {}".format(move_goal))
        move_base_client.send_goal(move_goal)
        # self.cancelNav()
        move_base_client.wait_for_result()
        return move_base_client.get_result()

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

    def point_head(self, x, y, z, frame):
        request = PointHeadRequestGoal()
        request.x = x
        request.y = y
        request.z = z
        request.frame = frame
        self.point_head_client.send_goal(request)
        self.point_head_client.wait_for_result()

    def pick(self, mode=0, goal=None):
        request = PickRequestGoal()
        request.mode = mode
        if goal:
            request.pick_pose = goal  # this is particle loc in map frame
        self.pick_client.send_goal(request)
        rospy.loginfo("Sent pick_client goal")
        self.pick_client.wait_for_result()
        res = self.pick_client.get_result()
        return res


class SFMClient():
    ''' 
        Main driver for running SFM experiments. 
    '''
    def __init__(self, experiment_config=None):
        # Experiment-specific stuff
        self.update = True # boolean controls whether we should update filters or not
        self.ac = ActionClient() # calls to action client
        self.neg_regions = set() # maintain negative regions
        self.regions = {} # maintain region priors
        self.experiment_config = experiment_config # config yaml
        self.record = rospy.get_param("~record") # are we recording a bag?
        self.kb = init_knowledge_base(rospy.get_param(
            '~sf_dir'), experiment_config['frames']) # init semantic frames
        self.state = State(experiment_config['action_history']) # init state
        for region in experiment_config['regions']:
            # build regions
            cubePoints = np.zeros((8,3))
            for i, point in enumerate(region['points']):
                cubePoints[i, 0] = float(point.split(",")[0])
                cubePoints[i, 1] = float(point.split(",")[1])
                cubePoints[i, 2] = float(point.split(",")[2])
            self.regions[region['name']] = Region(region['name'], 0, 0, 0, 0, 0, 0, cubePoints)
        self.observations = {}
        try:
            for observation in experiment_config['observations']:
                # self.observations[]
                self.object_filters[observation['name']].add_observation_from_config(
                    observation['x'], observation['y'], observation['z'])
        except:
            # no observations in the experiment config... that's fine
            pass

        # Filters
        self.object_filters = {} # build up a filter for each object we are tracking
        for object in experiment_config['objects']:
            name = object['name']
            priors = {}
            for prior in object['priors']:
                priors[self.regions[prior['name']]] = float(prior['weight'])
            self.object_filters[object['name']] = ObjectParticleFilter(
                50, valid_regions=priors, label=name, mapBox=self.regions['map'])
            self.object_filters[object['name']].publish()

        self.frame_filters = {} # build up a filter for each frame we are tracking
        for _, frame in enumerate(self.kb):
            filter = FrameParticleFilter(
                100, frame.name, frame.preconditions, frame.core_frame_elements, mapBox=self.regions['map'])
            filter.publish()
            for cfe in frame.core_frame_elements:
                # add objects for measurement potential
                filter.add_frame_element(self.object_filters[cfe], cfe)
            self.frame_filters[frame.name] = filter
            rospy.loginfo("{} filter initialized".format(frame.name))
        for frame in self.kb:
            for precondition in frame.preconditions:
                # add preconditions for context potential
                self.frame_filters[frame.name].add_precondition(
                    self.frame_filters[precondition], precondition)
        self.tf_listener = tf.TransformListener()
        # ROS subscribers
        self.observation_sub = rospy.Subscriber(
            'scene/observations', ObjectDetectionArray, self.handle_observation, queue_size=1) # msgs come from YOLO detections
        self.observationCount = 0
        self.execute_frame_sub = rospy.Subscriber(
            "/execute", String, self.execute_frame) # main cb for executing a frame

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

    def generateNegativeRegion(self):
        #Observable region is cube
        cube_length = 4
        #Constructing a cube in Camera Tilt Link
        cube_coord = np.zeros((8,3))
        #Bottom 4 points, going counter-clockwise from bottom left corner
        cube_coord[0] = np.array([0, 0.5*cube_length, -0.5*cube_length])
        cube_coord[1] = np.array([0, -0.5*cube_length, -0.5*cube_length])
        cube_coord[2] = np.array([cube_length, -0.5*cube_length, -0.5*cube_length])
        cube_coord[3] = np.array([cube_length, 0.5*cube_length, -0.5*cube_length])
        
        #Top 4 points, going counter-clockwise from top left corner
        cube_coord[4] = np.array([0, 0.5*cube_length, 0.5*cube_length])
        cube_coord[5] = np.array([0, -0.5*cube_length, 0.5*cube_length])
        cube_coord[6] = np.array([cube_length, -0.5*cube_length, 0.5*cube_length])
        cube_coord[7] = np.array([cube_length, 0.5*cube_length, 0.5*cube_length])        

        cube_in_map = np.zeros((8,3))
        #Transforming Observable region to map origin
        # rospy.logwarn("Map exists? {}".format(self.tf_listener.frameExists("/map")))
        # rospy.logwarn("Head tilt link exists? {}".format(self.tf_listener.frameExists("/head_tilt_link")))
        self.tf_listener.waitForTransform("/head_tilt_link", "/map", rospy.Time.now(), rospy.Duration(2.0))
        # if self.tf_listener.frameExists("/map") and self.tf_listener.frameExists("/head_tilt_link"):
        try:
            position, quaternion = self.tf_listener.lookupTransform(
                "/head_tilt_link",
                "/map",
                self.tf_listener.getLatestCommonTime("/head_tilt_link", "/map")
            )
            # rospy.logwarn("Current transform: {} quat: {}".format(position, quaternion))
            # rospy.logwarn("Transforming cube to map frame")
            for i in range(len(cube_coord)):
                point_in_robot = PoseStamped()
                point_in_robot.pose.position.x = cube_coord[i][0]
                point_in_robot.pose.position.y = cube_coord[i][1]
                point_in_robot.pose.position.z = cube_coord[i][2]
                point_in_robot.pose.orientation.x = 0
                point_in_robot.pose.orientation.y = 0
                point_in_robot.pose.orientation.z = 0
                point_in_robot.pose.orientation.w = 1

                point_in_robot.header.frame_id = "/head_tilt_link"
                point_in_robot.header.stamp = self.tf_listener.getLatestCommonTime("/head_tilt_link", "/map")

                point_transformed = self.tf_listener.transformPose('/map', point_in_robot)
            # self.transform_listener.waitForTransform("/head_camera_tilt_link", "/map", rospy.Time.now(), rospy.Duration(2.0))
            # try:
            #     pose_transformed = self.tf_listener.transformPose('/base_link', point_in_robot)
            # except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException, Exception) as e:
            #     rospy.loginfo("TF Exception... {}".format(e))
            #     return
                cube_in_map[i][0] = point_transformed.pose.position.x
                cube_in_map[i][1] = point_transformed.pose.position.y
                cube_in_map[i][2] = point_transformed.pose.position.z
        except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException, Exception) as e:
            rospy.loginfo("TF Exception... {}".format(e))
            return None
        return cube_in_map

    def handle_observation(self, msg):
        # rospy.logwarn("Handling observation")
        self.observationCount +=1
        objectsSeen = set()
        # rospy.logwarn(msg)
        for detection in msg.detections:
            # rospy.logwarn(detection.label)
            objectsSeen.add(detection.label)
            try:
                self.object_filters[detection.label].add_observation(detection)
            except KeyError:
                # not tracking the object we detected
                pass
        cube_in_map = self.generateNegativeRegion()
        if cube_in_map is None:
            rospy.logerr("Could not generate cube_in_map")
            return
        reg = Region("Neg_reg_{}".format(self.observationCount), 0, 0, 0, 0, 0, 0, cube_in_map)   
        for label, filter in self.object_filters.items():
            if label not in objectsSeen:
                # add negative region
                rospy.logwarn("Adding negative region to {}".format(label))
                filter.add_negative_region(reg)

    def publish_regions(self):
        for region in self.regions.values():
            region.publish()
        for region in self.neg_regions:
            region.publish()

    def update_filters(self, publish=True):
        if not self.update:
            return
        for _, filter in self.object_filters.items():
            filter.update_filter()
            if publish:
                filter.publish()
        for _, filter in self.frame_filters.items():
            filter.update_filter(self.state)
            if publish:
                filter.publish()

    def add_observations(self, possible_observations=[]):
        '''
            Only used in simulation 
        '''
        # add observations if they are within 5m of the robot's current pose, else add negative region
        cur_pose = self.state.pose
        for _, filter in self.object_filters.items():
            added = False
            for observation in possible_observations:
                x_dist = (observation['x'] - cur_pose.position.x)**2
                y_dist = (observation['y'] - cur_pose.position.y)**2
                if np.sqrt(x_dist + y_dist) <= 5.0:
                    filter.add_observation_from_config(
                        observation['x'], observation['y'], observation['z'])
                    added = True
            if not added:
                min_x = cur_pose.position.x - 2
                max_x = cur_pose.position.x + 2
                min_y = cur_pose.position.y - 2
                max_y = cur_pose.position.y + 2
                min_z = 0
                max_z = 1.5
                reg = Region("{}_neg_reg_{}".format(filter.label, len(
                    self.neg_regions)), min_x, max_x, min_y, max_y, min_z, max_z)
                filter.add_negative_region(reg)
                self.neg_regions.add(reg)
           
    def run_observation_routine(self, object_detections=[], frame=None):  #added object_detections as input
        """
        Only used in simulation.
        This is a simulated object detection method
            
        If the robot in near or in a region that an object is in, we add the observation
        else, add that region as a negative obersvation region for that object
        
        """
        #Observable region is cube
        cube_length = 2
        #Constructing a cube in Camera Tilt Link
        cube_coord = np.zeros((8,3))
        #Bottom 4 points, going counter-clockwise from bottom left corner
        cube_coord[0] = np.array([0, 0.5*cube_length, -0.5*cube_length])
        cube_coord[1] = np.array([0, -0.5*cube_length, -0.5*cube_length])
        cube_coord[2] = np.array([cube_length, -0.5*cube_length, -0.5*cube_length])
        cube_coord[3] = np.array([cube_length, 0.5*cube_length, -0.5*cube_length])
        
        #Top 4 points, going counter-clockwise from top left corner
        cube_coord[4] = np.array([0, 0.5*cube_length, 0.5*cube_length])
        cube_coord[5] = np.array([0, -0.5*cube_length, 0.5*cube_length])
        cube_coord[6] = np.array([cube_length, -0.5*cube_length, 0.5*cube_length])
        cube_coord[7] = np.array([cube_length, 0.5*cube_length, 0.5*cube_length])        

        cube_in_map = np.zeros((8,3))
        #Transforming Observable region to map origin
        # rospy.logwarn("Map exists? {}".format(self.tf_listener.frameExists("/map")))
        # rospy.logwarn("Head tilt link exists? {}".format(self.tf_listener.frameExists("/head_tilt_link")))
        self.tf_listener.waitForTransform("/head_tilt_link", "/map", rospy.Time.now(), rospy.Duration(2.0))
        # if self.tf_listener.frameExists("/map") and self.tf_listener.frameExists("/head_tilt_link"):
        try:
            position, quaternion = self.tf_listener.lookupTransform(
                "/head_tilt_link",
                "/map",
                self.tf_listener.getLatestCommonTime("/head_tilt_link", "/map")
            )
            rospy.logwarn("Current transform: {} quat: {}".format(position, quaternion))
            rospy.logwarn("Transforming cube to map frame")
            for i in range(len(cube_coord)):
                point_in_robot = PoseStamped()
                point_in_robot.pose.position.x = cube_coord[i][0]
                point_in_robot.pose.position.y = cube_coord[i][1]
                point_in_robot.pose.position.z = cube_coord[i][2]
                point_in_robot.pose.orientation.x = 0
                point_in_robot.pose.orientation.y = 0
                point_in_robot.pose.orientation.z = 0
                point_in_robot.pose.orientation.w = 1

                point_in_robot.header.frame_id = "/head_tilt_link"
                point_in_robot.header.stamp = self.tf_listener.getLatestCommonTime("/head_tilt_link", "/map")

                point_transformed = self.tf_listener.transformPose('/map', point_in_robot)
            # self.transform_listener.waitForTransform("/head_camera_tilt_link", "/map", rospy.Time.now(), rospy.Duration(2.0))
            # try:
            #     pose_transformed = self.tf_listener.transformPose('/base_link', point_in_robot)
            # except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException, Exception) as e:
            #     rospy.loginfo("TF Exception... {}".format(e))
            #     return
                cube_in_map[i][0] = point_transformed.pose.position.x
                cube_in_map[i][1] = point_transformed.pose.position.y
                cube_in_map[i][2] = point_transformed.pose.position.z
        except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException, Exception) as e:
            rospy.loginfo("TF Exception... {}".format(e))
            return

        # print(cube_in_map) #Observable region in map

        for _,filter in self.object_filters.items():
            obj_seen = False
            for detection in object_detections:
                if self.label == detection.label:
                    obj_seen = True
                    ## Add observation to filter

                    break
                
                # if filter.label == detection.label and self.check_point_in_cube(cube_in_map, point):
                #     reg = Region("{}_valid_reg_{}".format(filter.label, len(self.valid_regions)), min_x, max_x, min_y, max_y, min_z, max_z)
                #     filter.add_valid_region(reg)
                #     self.valid_regions.add(reg)
                
                #point = np.array([detection.pose.position.x, detection.pose.position.y, detection.pose.position.z])

            if not obj_seen: #and not self.check_point_in_cube(cube_in_map, point):  
                min_x = np.amin(cube_in_map[:,0])
                max_x = np.amax(cube_in_map[:,0])
                min_y = np.amin(cube_in_map[:,1])
                max_y = np.amax(cube_in_map[:,1])
                min_z = np.amin(cube_in_map[:,2])   
                max_z = np.amax(cube_in_map[:,2])
                # reg = Region("{}_neg_reg_{}".format(filter.label, len(filter.negative_regions)), min_x, max_x, min_y, max_y, min_z, max_z)
                reg = Region("{}_neg_reg_{}".format(filter.label, len(filter.negative_regions)), min_x, max_x, min_y, max_y, min_z, max_z, cube_in_map)
                rospy.logwarn("Adding negative Region")                  
                filter.add_negative_region(reg)
                # self.neg_regions.add(reg)
                
    def dist(self, robot, obj):
        x_dist = np.abs(robot.position.x - obj.x)
        y_dist = np.abs(robot.position.y - obj.y)
        # z_dist = np.abs(robot.position.z - obj.z)
        return np.sqrt(x_dist**2 + y_dist**2)

    def graspObject(self, object: str, frameFilter: FrameParticleFilter) -> bool:
        '''
            Execution routine for grasping an object
            Args:
                object (str): name of object we want to grasp
                frameFilter (FrameParticleFilter): filter for distribution of grasp_{object}
            Returns:
                res (bool): True if grasp was successful, False otherwise
        '''
        rospy.loginfo("[AGENT]: Entering graspObj({}, {})".format(
            object, frameFilter.label))
        objGrasped = False
        while not frameFilter.converged:
            self.searchFor(object)
        rospy.sleep(10) # let filters update
        self.update = False # pause filter updates
        best_particle = frameFilter.maxParticle#getHighestWeightedParticle()
        dist = 1e3
        keyposeGoal = None
        for name, keypose in self.state.keyposes.items():
            xdist = np.abs(keypose.pose.position.x - best_particle[0])**2
            ydist = np.abs(keypose.pose.position.y - best_particle[1])**2
            distToKeypose = np.sqrt(xdist + ydist)
            if distToKeypose < dist:
                dist = distToKeypose
                keyposeGoal = keypose
            # dist = min(dist, ())
        rospy.logwarn("Nav to keypose: {}".format(keyposeGoal))
        self.ac.goToKeyPose(keyposeGoal)
        self.ac.cancelNav()
        rospy.sleep(2)     
        # self.ac.point_head(0.8, 0.0, 0.8, "base_link")
        rospy.logwarn("Particle loc: ({:.6f}, {:.6f}, {:.6f}".format(best_particle[0], best_particle[1], best_particle[2]))
        self.ac.point_head(best_particle[0], best_particle[1], best_particle[2], "map")
        pick_pose = Pose()
        pick_pose.position.x = best_particle[0]
        pick_pose.position.y = best_particle[1]
        pick_pose.position.z = best_particle[2]
        rospy.logwarn("Sending pick location to picker")
        self.ac.pick(mode=0, goal=pick_pose)
        self.state.add_action_to_action_history(frameFilter.label)
        self.state.grasped_object = object
        return True

    def putObject(self, object, target, frameFilter: FrameParticleFilter) -> bool:
        '''
            Execution routine for placing an object
            Args:
                object (str): name of object we want to place
                target (str): name of object we want to place {object} onto
                frameFilter (FrameParticleFilter): filter for distribution of place_{object}
            Returns:
                res (bool): True if grasp was successful, False otherwise
        '''
        print("[AGENT]: Entering putObject({}, {}, {})".format(object, target, frameFilter.label))
        keyposeGoal = self.state.keyposes['bar_table']
        self.ac.goToKeyPose(keyposeGoal)
        self.ac.point_head(1, 0, 0.8, 'base_link')
        place_pose = PoseStamped()
        place_pose.header.frame_id = "map"
        place_pose.header.stamp = rospy.Time.now()
        place_pose.pose.position.x = -1.5
        place_pose.pose.position.y = -10.5
        place_pose.pose.position.z = 0.9
        # place_pose_map_frame = self.tf_listener.transformPose("/map", place_pose)
        self.ac.pick(mode=2, goal=place_pose.pose)
        return True
        # TODO: Implement this checking if frameFilter is converged, picking navGoal, navigating and then attempting to put object on target
        # rospy.loginfo("[AGENT]: Entering graspObj({}, {})".format(
        #     object, frameFilter.label))
        # objGrasped = False
        # while not frameFilter.converged:
        #     rospy.loginfo_throttle(1, "Waiting for filter to converge....")
        #     self.searchFor(object)
        #     rospy.sleep(5) # let filters update
        # self.ac.cancelNav()
        # rospy.sleep(5)
        # self.update = False # pause filter updates
        # best_particle = frameFilter.getHighestWeightedParticle()
        # dist = 1e3
        # keyposeGoal = None
        # for keypose in self.state.keyposes:
        #     xdist = np.abs(keypose.pose.position.x - best_particle[0])**2
        #     ydist = np.abs(keypose.pose.position.y - best_particle[1])**2
        #     distToKeypose = np.sqrt(xdist + ydist)
        #     if distToKeypose < dist:
        #         dist = distToKeypose
        #         keyposeGoal = keypose
            # dist = min(dist, ())

    def stirObject(self, object, target, frameFilter: FrameParticleFilter)->bool:
        # TODO: Implement this checking if frameFilter is converged, picking navGoal, navigating and then attempting to stir target with object
        print("[AGENT]: Entering stirObject({}, {}, {})".format(
            object, target, frameFilter.label))

    def pourObject(self, object, target, frameFilter: FrameParticleFilter) -> bool:
        print("[AGENT]: Entering pourObject({}, {}, {})".format(
            object, target, frameFilter.label))
        # TODO: Implement this checking if frameFilter is converged, picking navGoal, navigating and then attempting to pour obj into target
        # while not frameFilter.converged:
        #     self.searchFor(object)
        rospy.sleep(10) # let filters update
        self.update = False # pause filter updates
        best_particle = frameFilter.maxParticle#getHighestWeightedParticle()
        dist = 1e3
        keyposeGoal = None
        for name, keypose in self.state.keyposes.items():
            xdist = np.abs(keypose.pose.position.x - best_particle[0])**2
            ydist = np.abs(keypose.pose.position.y - best_particle[1])**2
            distToKeypose = np.sqrt(xdist + ydist)
            if distToKeypose < dist:
                dist = distToKeypose
                keyposeGoal = keypose
            # dist = min(dist, ())
        rospy.logwarn("Nav to keypose: {}".format(keyposeGoal))
        self.ac.goToKeyPose(keyposeGoal)
        self.ac.cancelNav()
        # self.ac.point_head(1, 0, 0.8, 'base_link')
        # best_particle = self.frame_filters['pour_cereal_bowl'].maxParticle
        # self.ac.point_head(0.8, 0, 0.8, "base_link")
        self.ac.point_head(best_particle[0], best_particle[1], best_particle[2], "map")
        self.ac.pick(mode=3,goal=None)
        return True


    def searchFor(self, object_name): #returns next beleived pose position
        # self.update = False
        mean = self.object_filters[object_name].latest_bgmm_mean        
        goal_x = mean[0]
        goal_y = mean[1]
        # rospy.logwarn(f"In Searchfor bgmm mean is {mean}")
        self.ac.go_to(goal_x, goal_y, 0)
        self.ac.cancelNav() # stop moving
        self.ac.point_head(goal_x, goal_y, 0.8, "map")
        self.ac.run_yolo() # get observation
    
    def execute_frame(self, frame_name: String):
        self.ac.run_yolo()
        rospy.sleep(2)
        self.execute(frame_name.data)

    def execute(self, frame_name: str):
        frameFilter = self.frame_filters[frame_name]
        try:
            uncompletedPreconditions = [
                pre
                for pre in frameFilter.preconditions
                if pre not in self.state.action_history
            ]
            print("[AGENT]: Uncompleted Preconditions for {} are: {}".format(
                frame_name, uncompletedPreconditions
            ))
            for precondition in uncompletedPreconditions:
                if self.execute(precondition):
                    print("[AGENT]: Action history: {}".format(
                        self.state.action_history))
                    print("[AGENT]: Updating Filters after successful execution")
                    self.update = True
                    rospy.sleep(10)  # sleep for 10s
                else:
                    print("[AGENT]: Precondition {} failed".format(precondition))
        except TypeError:
            print("[AGENT]: No preconditions for {}".format(frame_name))

        if frame_name.split("_")[0] == "grasp":
            return self.graspObject(frame_name.split("_", 1)[1], frameFilter)
        
        elif frame_name.split("_")[0] == "put":
            return self.putObject("foo", "bar", frameFilter)
        
        elif frame_name.split("_")[0] == "pour":
            '''
            if pour_object != self.state.grasped_object -> Raise Exception
            
            '''
            return self.pourObject(self.state.grasped_object, "bowl", frameFilter)



    def run(self):
        '''
            Use this function to run quick demos
        '''
        self.execute_frame('pour_cereal_bowl')
        #OR
        #the step by step method
        # frame_name = 'grasp_cracker_box'
        # frameFilter = self.frame_filters[frame_name]
        # ## initialize filters
        # rospy.logwarn("Updating filters 50 times")
        # for ii in range(50):
        #     self.update_filters(publish=True)
        # ## Run Detection
        # rospy.logwarn("Running Detections")
        # self.ac.run_yolo()
        # for ii in range(100):
        #     self.update_filters(publish=True)
        # if self.graspObject(frame_name.split("_", 1)[1], frameFilter):
        # # # if self.graspObject("cracker_box", "grasp_cracker_box_sf"):
        #     rospy.logwarn("Picked crackerbox")
        #     self.object_filters['bowl'].handle_ar = True
        #     self.pourObject('bowl', 'pour_cereal_bowl')            
            # best_particle = self.frame_filters['pour_cereal_bowl'].maxParticle
            # self.ac.point_head(best_particle[0], best_particle[1], best_particle[2], "map")
            # self.ac.pick(mode=3,goal=None)


        # self.object_filters['bowl'].handle_ar = True
        # rospy.logwarn("Updating filters 100 times")
        # ## Update Filters 100 times
        # for ii in range(100):
        #     self.update_filters(publish=True)
        # rospy.logwarn("Pour crackerbox into bowl")
        # ## Call action client pick with mode 3
        # best_particle = self.frame_filters['pour_cereal_bowl'].maxParticle
        # self.ac.point_head(best_particle[0], best_particle[1], best_particle[2], "map")
        # pick_pose = Pose()
        # pick_pose.position.x = best_particle[0]
        # pick_pose.position.y = best_particle[1]
        # pick_pose.position.z = best_particle[2]
        # if self.ac.pick(mode=0, goal=pick_pose):
        #     rospy.logwarn("Picked crackerbox")
        #     self.state.add_action_to_action_history("grasp_cracker_box")
        #     for ii in range(100):
        #         self.update_filters(publish=True)
        #     rospy.logwarn("Pouring crackerbox into bowl")
        #     best_particle = self.frame_filters['pour_cereal_bowl'].maxParticle
        #     self.ac.point_head(best_particle[0], best_particle[1], best_particle[2], "map")
        #     self.ac.pick(mode=3,goal=None)
            




        # while not rospy.is_shutdown():
        #     rospy.logwarn("Going to collab table")
        #     suc = self.ac.goToKeyPose(self.state.collab_table)
        #     if suc:
        #         rospy.logwarn("Made it to collabe table")
        #     else:
        #         rospy.logwarn("FAILURE: Collab table")
        #     rospy.logwarn("Going to light table")
        #     suc = self.ac.goToKeyPose(self.state.light_table)
        #     if suc:
        #         rospy.logwarn("Made it light table")
        #     else:
        #         rospy.logwarn("FAILURE: light table")
        #     rospy.logwarn("Going to bar table")
        #     suc = self.ac.goToKeyPose(self.state.bar_table)
        #     if suc:
        #         rospy.logwarn("Made it to bar table")
        #     else:
        #         rospy.logwarn("FAILURE: Bar table")

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
        # for i in range(100):
        #     self.update_filters(publish=True)
        # rospy.logwarn("Running observation routine")
        # self.run_observation_routine()
        # while not rospy.is_shutdown():
        #     if self.update:
        #         # rospy.logwarn_throttle(1, "UPdating filters")
        #         self.update_filters(publish=True)
        #         # self.publish_regions()
        #     else:
        #         pass

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

    # ac = ActionClient()
    # Move the base to be in front of the table
    # Demonstrates the use of the navigation stack
    # rospy.loginfo("Moving to table...")
    # ac.go_to(6, -5.4, -1.57079632679)
    # move_base.goto(2.750, 3.118, 0.0)

    # # Raise the torso using just a controller
    # rospy.loginfo("Raising torso...")
    # ac.move_torso(0.4)

    # # Point the head at the cube we want to pick
    # ac.point_head(6.8, -6, 0.8)

    # ac.pick(mode=0)
    # ac.pick(mode=1) # mode == 1 --> tuck_arm
    # ac.move_torso(0.0)

    # # Get block to pick
    # while not rospy.is_shutdown():
    #     rospy.loginfo("Picking object...")
    #     grasping_client.updateScene()
    #     cube, grasps = grasping_client.getGraspableCube()
    #     if cube == None:
    #         rospy.logwarn("Perception failed.")
    #         continue

    #     # Pick the block
    #     if grasping_client.pick(cube, grasps):
    #         break
    #     rospy.logwarn("Grasping failed.")

    # # # Tuck the arm
    # grasping_client.tuck()

    # # # Lower torso
    # rospy.loginfo("Lowering torso...")
    # torso_action.move_to([0.0, ])

    # rospy.loginfo("Done!")
    # gloc_client = actionlib.SimpleActionClient('grasploc_requests', GrasplocRequestAction)
    # gloc_client.wait_for_server()
    # goal = GrasplocRequestGoal()
    # goal.tmp = 0
    # gloc_client.send_goal(goal)
    # gloc_client.wait_for_result()
    # result = gloc_client.get_result()
    # print(result)

    """
    ac = ActionClient()
    # siny_cosp = 2 * (0.832 * -0.490778743358)
    # cosy_cosp = 1 - 2*(-0.490778743358**2)
    # t = np.arctan2(siny_cosp, cosy_cosp) - 0.6
    
    # ac.go_to(-5.988, -33.000, -2.657)
    # ready_pose = Pose()
    # ready_pose.position.x = 0.388766448993
    # ready_pose.position.y = 0.378542124739
    # ready_pose.position.z = 1.04805824777
    # ready_pose.orientation.x = -0.0978119668855
    # ready_pose.orientation.y = 0.586970796926
    # ready_pose.orientation.z = 0.0532830679297
    # ready_pose.orientation.w = 0.801909606727
    # ac.pick(mode=0,goal=ready_pose)
    # pre_grasp_pose = Pose()
    # pre_grasp_pose.position.x = 0.706376829351
    # pre_grasp_pose.position.y = 0.327823473247
    # pre_grasp_pose.position.z = 0.942892063785
    # pre_grasp_pose.orientation.x = -0.000825113383771
    # pre_grasp_pose.orientation.y = 0.0465757301487
    # pre_grasp_pose.orientation.z = -0.598691337224
    # pre_grasp_pose.orientation.w = 0.799624101239
    # ac.pick(mode=0, goal=pre_grasp_pose)
    # grasp_pose = Pose()
    # grasp_pose.position.x = 0.730670415859
    # grasp_pose.position.y = 0.0817700400619
    # grasp_pose.position.z = 0.944080491806
    # grasp_pose.orientation.x = -0.0586105500584
    # grasp_pose.orientation.y = -0.00751916695798
    # grasp_pose.orientation.z = -0.618539099892
    # grasp_pose.orientation.w = 0.783528970399
    # ac.pick(mode=1, goal=grasp_pose)
    drop_pose = Pose()
    drop_pose.position.x = 0.742431761974
    drop_pose.position.y = 0.166189923673
    drop_pose.position.z = 1.211409257298
    drop_pose.orientation.x = 0.0964181423434
    drop_pose.orientation.y = 0.0668233573068
    drop_pose.orientation.z = -0.600939682408
    drop_pose.orientation.w = 0.790638778996
    ac.pick(mode=0, goal=drop_pose)
    """

    with open(rospy.get_param("~experiment_config"), 'r') as file:
        experiment_config = yaml.safe_load(file)
    foo = SFMClient(experiment_config)
    rospy.loginfo("SFM Client successfully initialized... Beginning {}".format(
        experiment_config['title']))
    # while not rospy.is_shutdown():
    #     choice = input("Press y to run")
    #     if choice == 'y':
    #         foo.run()
    #     rospy.spin()
      
    # foo.irosVideo()
    while not rospy.is_shutdown():
        foo.update_filters()

    # r = rospy.Rate(1000)
    # i = 0
    # while not rospy.is_shutdown():
    #     rospy.spin()
    #     if i < 20:
    #     #     print("ITR: {}".format(i+1))
    #     #     # if i == 100:
    #     #     #     foo.go_to()
    #     #     # rospy.loginfo("Updating...")
    #     foo.update_filters()
    #     foo.publish_regions()
    #     #     # print(foo.state.action_history)
    #     #     # rospy.loginfo(i)
    #     #     # if i == 10:
    #     #     #     foo.frame_filters['grasp_bottle'].bgmm()
    #     #     i+=1
    #     r.sleep()
