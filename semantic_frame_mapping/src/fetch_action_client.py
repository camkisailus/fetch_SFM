#! /usr/bin/python3

import rospy
from fetch_actions.msg import MoveBaseRequestAction, MoveBaseRequestGoal, TorsoControlRequestAction, TorsoControlRequestGoal, PointHeadRequestAction, PointHeadRequestGoal, PickRequestAction, PickRequestGoal
import actionlib
class ActionClient():
    def __init__(self):
        # self.make_plan_client = rospy.ServiceProxy('move_base/make_plan', GetPlan)

        self.move_base_client = actionlib.SimpleActionClient("kisailus_move_base", MoveBaseRequestAction)
        self.move_base_client.wait_for_server()
        rospy.logwarn("Connected to move_base server")
        self.torso_client = actionlib.SimpleActionClient("kisailus_torso_controller", TorsoControlRequestAction)
        self.torso_client.wait_for_server()
        rospy.logwarn("Connected to torso client")
        self.point_head_client = actionlib.SimpleActionClient("kisailus_point_head", PointHeadRequestAction)
        self.point_head_client.wait_for_server()
        rospy.logwarn("Connected to point head client")
        # self.pick_client = actionlib.SimpleActionClient("kisailus_pick", PickRequestAction)
        # self.pick_client.wait_for_server()
        # rospy.logwarn("Connected to pick server")
        # self.pick_sub = rospy.Subscriber("pick", Bool, self.pick_from_cmd)
        # self.tf_listener = tf.TransformListener()
        # self.grasp_pub = rospy.Publisher('request_grasp_pts', Bool, queue_size=10)
        # self.point_head_pub = rospy.Publisher('/point_head/at', Point, queue_size=10)
        # self.cur_pose_sub = rospy.Subscriber("/amcl_pose", PoseWithCovarianceStamped, self.pose_cb)
        # self.cur_pose = Pose()

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
        request = PickRequestGoal()
        request.mode = mode
        if goal:
           request.pick_pose = goal # this is particle loc in map frame
        self.pick_client.send_goal(request)
        rospy.loginfo("Sent pick_client goal")
        self.pick_client.wait_for_result()
        res = self.pick_client.get_result()
        return res
