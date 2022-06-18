#! /usr/bin/python3

import rospy
import copy
import math
import actionlib
import tf
import numpy as np

from scipy.spatial.transform import Rotation as R
from geometry_msgs.msg import Pose, PointStamped, PoseStamped, PoseArray
from moveit_python import MoveGroupInterface, PlanningSceneInterface, PickPlaceInterface
from moveit_python.geometry import rotate_pose_msg_by_euler_angles
from grasping_msgs.msg import FindGraspableObjectsAction, FindGraspableObjectsGoal
from moveit_msgs.msg import PlaceLocation, MoveItErrorCodes, Grasp, GripperTranslation
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from std_msgs.msg import Bool



class GraspingClient(object):
    def __init__(self):
        self.observation_pub = rospy.Publisher('scene/observations', Pose, queue_size=10)
        self.request_grasp_pub = rospy.Publisher('request_grasp_pts', Bool, queue_size=10)
        self.tf_listener = tf.TransformListener()
        self.scene = PlanningSceneInterface('base_link')
        self.pickplace = PickPlaceInterface('arm', 'gripper', verbose=True)
        self.move_group = MoveGroupInterface('arm', 'base_link')
        self.grasploc_sub = rospy.Subscriber('grasploc', PoseArray, self.grasp_callback)
        self.grasp_pose_pub = rospy.Publisher('kisailus_gp', PointStamped, queue_size=10)
        self.grasp_posegt_pub = rospy.Publisher('gt_gp', PointStamped, queue_size=10)
        
        find_topic = 'basic_grasping_perception/find_objects'
        rospy.loginfo("Waiting for %s..." % find_topic)
        self.find_client = actionlib.SimpleActionClient(find_topic, FindGraspableObjectsAction)
        self.find_client.wait_for_server()
        rospy.loginfo("Done")
    
    def make_grasp_posture(self, pose):
        trajectory = JointTrajectory()
        trajectory.joint_names.append('r_gripper_finger_joint')
        trajectory.joint_names.append('l_gripper_finger_joint')
        point = JointTrajectoryPoint()
        point.positions.append(pose/2.0)
        point.positions.append(pose/2.0)
        point.effort.append(50.0)
        point.effort.append(50.0)
        point.time_from_start = rospy.Duration(2.0)
        trajectory.points.append(point)
        return trajectory


    def make_gripper_translation(self, frame, min_dist, desired, x_axis=1.0, y_axis=0.0, z_axis=0.0):
        translation = GripperTranslation()
        translation.direction.vector.x = x_axis
        translation.direction.vector.y = y_axis
        translation.direction.vector.z = z_axis
        translation.direction.header.frame_id = frame
        translation.min_distance = min_dist
        translation.desired_distance = desired
        return translation

    
    def grasp_callback(self, msg):
        if len(msg.poses) == 0:
            rospy.logwarn("NO VALID GRASPS RETURNED FROM GRASPLOC")
            return
        rospy.loginfo("Got grasp poses from grasploc")
        grasps = []
        for grasp_pose in msg.poses:
            grasp = Grasp()
            grasp.grasp_pose.header.frame_id = 'base_link'
            grasp.grasp_pose.pose = grasp_pose
            grasp.pre_grasp_posture = self.make_grasp_posture(0.05)
            grasp.grasp_posture = self.make_grasp_posture(0.0)
            grasp.pre_grasp_approach = self.make_gripper_translation("wrist_roll_link", 0.1, 0.15)
            grasp.post_grasp_retreat = self.make_gripper_translation("wrist_roll_link", 0.1, 0.15, -1.0)
            grasps.append(grasp)
        

        obj_name = None
        min_dist = None
        self.updateScene()
        for obj in self.objects:
            x_dist = math.pow(obj.object.primitive_poses[0].position.x-grasp_pose.position.x, 2)
            y_dist = math.pow(obj.object.primitive_poses[0].position.y - grasp_pose.position.y, 2)
            z_dist = math.pow(obj.object.primitive_poses[0].position.z - grasp_pose.position.z, 2)
            dist = math.sqrt(x_dist + y_dist + z_dist)
            if min_dist == None:
                min_dist = dist
                obj_name = obj.object.name
            elif dist < min_dist:
                min_dist = dist
                obj_name = obj.object.name

        rospy.loginfo("Attempting to pick {}".format(obj_name))
        self.pickplace.pick_with_retry(obj_name, grasps, scene=self.scene)
        # self.tuck()
        
    def clearScene(self):
        for name in self.scene.getKnownCollisionObjects():
            self.scene.removeCollisionObject(name, use_service=False)
        for name in self.scene.getKnownAttachedObjects():
            self.scene.removeAttachedObject(name, use_service=False)

    def updateScene(self):
        goal = FindGraspableObjectsGoal()
        goal.plan_grasps = False
        self.find_client.send_goal(goal)
        self.find_client.wait_for_result(rospy.Duration(5.0))

        find_result = self.find_client.get_result()
        self.clearScene()
        idx = -1
        rospy.loginfo("Found {} objects".format(len(find_result.objects)))
        for obj in find_result.objects:
            if obj.object.primitive_poses[0].position.z <= 0.25:
                continue
            if obj.object.primitive_poses[0].position.x >= 0.8:
                # Remove detections that are far
                continue
            idx += 1
            obj.object.name = 'object_{}'.format(idx)
            self.scene.addSolidPrimitive(obj.object.name, obj.object.primitives[0], obj.object.primitive_poses[0], use_service=False)
            self.scene.addSolidPrimitive()
        for obj in find_result.support_surfaces:
            height = obj.primitive_poses[0].position.z
            obj.primitives[0].dimensions = [obj.primitives[0].dimensions[0]+0.2, obj.primitives[0].dimensions[1]+0.2, obj.primitives[0].dimensions[2] + height]
            obj.primitive_poses[0].position.z += -height/2.0
            self.scene.addSolidPrimitive(obj.name, obj.primitives[0], obj.primitive_poses[0], use_service=False)
        
        self.objects = find_result.objects
        self.surfaces = find_result.support_surfaces

    def tuck(self):
        joints = ["shoulder_pan_joint", "shoulder_lift_joint", "upperarm_roll_joint",
                  "elbow_flex_joint", "forearm_roll_joint", "wrist_flex_joint", "wrist_roll_joint"]
        pose = [1.32, 1.40, -0.2, 1.72, 0.0, 1.66, 0.0]
        while not rospy.is_shutdown():
            result = self.move_group.moveToJointPosition(joints, pose, 0.02)
            if result.error_code.val == MoveItErrorCodes.SUCCESS:
                return

    def publish_observation(self, observation):
        pt = PointStamped()
        pt.header.frame_id = 'base_link'
        pt.point.x = observation.primitive_poses[0].position.x
        pt.point.y = observation.primitive_poses[0].position.y
        pt.point.z = observation.primitive_poses[0].position.z
        base_link_point = self.tf_listener.transformPoint("map", pt)
        pose = Pose()
        pose.position.x = base_link_point.point.x
        pose.position.y = base_link_point.point.y
        pose.position.z = base_link_point.point.z
        pose.orientation.w = 1.0
        self.observation_pub.publish(pose)
    
    
    
    def getSupportSurface(self, name):
        for surface in self.surfaces:
            if surface.name == name:
                return surface
        return None
    
    def getPlaceLocation(self):
        pass

    
    def place(self, block, pose_stamped):
        places = list()
        l = PlaceLocation()
        l.place_pose.pose = pose_stamped.pose
        l.post_place_posture = self.pick_result.grasp.pre_grasp_posture
        l.pre_place_approach = self.pick_result.grasp.pre_grasp_approach
        l.post_place_retreat = self.pick_result.grasp.post_grasp_retreat
        places.append(copy.deepcopy(l))

        m = 16
        pi = math.pi
        for i in range(0, m-1):
            l.place_pose.pose = rotate_pose_msg_by_euler_angles(l.place_pose.pose, 0, 0, 2*pi/i)
            places.append(copy.deepcopy(l))
        
        success, place_result = self.pickplace.place_with_retry(block.name, places, scene=self.scene)

        return success
    

if __name__ == '__main__':
    rospy.init_node('grasping_client')
    grasping_client = GraspingClient()
    grasping_client.updateScene()
    grasping_client.tuck()
    r = rospy.Rate(10)
    while not rospy.is_shutdown():
        r.sleep()