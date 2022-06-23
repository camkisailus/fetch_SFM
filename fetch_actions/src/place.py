#! /usr/bin/python

import rospy
import sys
import actionlib

from moveit_commander import PlanningSceneInterface, roscpp_initialize, roscpp_shutdown, MoveGroupCommander
from geometry_msgs.msg import PoseStamped, Point
from moveit_msgs.msg import Grasp, PlaceLocation
from trajectory_msgs.msg import JointTrajectoryPoint
from grasping_msgs.msg import FindGraspableObjectsAction, FindGraspableObjectsGoal
from fetch_actions.msg import PlaceRequestAction
from grasploc_wrapper_msgs.msg import GrasplocRequestAction, GrasplocRequestGoal
from semantic_frame_mapping.msg import ObjectDetection

class GraspableObject:
    def __init__(self, name, pose):
        self.name = name
        self.pose = pose

class PlaceClient:
    def __init__(self):
        roscpp_initialize(sys.argv)
        self.scene = PlanningSceneInterface()
        self.arm = MoveGroupCommander('arm', wait_for_servers=30)
        self.request_server = actionlib.SimpleActionServer('kisailus_place', PlaceRequestAction, self.callback, auto_start=False)
        self.request_server.start()
        rospy.sleep(1)
        # self.grasploc_sub = rospy.Subscriber('grasploc', PoseArray, self.grasploc_cb)

    def callback(self, request):
        rospy.loginfo("PLACE_NODE: Got a request...")
        self.place()
        rospy.loginfo("PLACE_NODE: Placed obj...")

    def place(self):
        goal = PlaceLocation()
        goal.place_pose.header.frame_id = 'base_link'
        goal.place_pose.pose.position.x = 0.4
        goal.place_pose.pose.position.y = 0.15
        goal.place_pose.pose.position.z = 0.75
        goal.place_pose.pose.orientation.w = 1.0
        goal.pre_place_approach.direction.header.frame_id = 'wrist_roll_link'
        goal.pre_place_approach.direction.vector.z = -1.0
        goal.pre_place_approach.min_distance = 0.1
        goal.pre_place_approach.desired_distance = 0.15
        goal.post_place_retreat.direction.header.frame_id = 'base_link'
        goal.post_place_retreat.direction.vector.z = 1.0
        goal.post_place_retreat.min_distance = 0.15
        goal.post_place_retreat.desired_distance = 0.2
        goal.post_place_posture.joint_names = ['r_gripper_finger_joint', 'l_gripper_finger_joint']
        pos = JointTrajectoryPoint()
        pos.positions.append(0.05) # all the way open
        pos.positions.append(0.05)
        pos.time_from_start = rospy.Duration(3)
        goal.post_place_posture.points.append(pos)
        # rospy.logwarn(self.scene.get_attached_objects())
        self.arm.place('object_0', goal)

    # def update_scene(self):
    #     goal = FindGraspableObjectsGoal()
    #     goal.plan_grasps = False
    #     self.find_client.send_goal(goal)
    #     self.find_client.wait_for_result()
    #     find_result = self.find_client.get_result()
    #     idx = -1
    #     for obj in find_result.objects:
    #         if obj.object.primitive_poses[0].position.z <= 0.6 or obj.object.primitive_poses[0].position.x >= 1.5:
    #             continue
    #         # if obj.object.primitive_poses[0].position.x >= 0.8:
    #         #     # Remove detections that are far
    #         #     continue
    #         idx += 1
    #         obj.object.name = 'object_{}'.format(idx)
            
    #         # rospy.loginfo(obj.object)
    #         obj_pose = PoseStamped()
    #         obj_pose.pose = obj.object.primitive_poses[0]
    #         obj_pose.header.frame_id = 'base_link'
    #         # self.graspable_objs.append(GraspableObject(obj.object.name, obj_pose))
    #         # obs_msg = ObjectDetection()
    #         # transformed_pt = self.tf_listener.transformPose('map', obj_pose)
    #         # obs_msg.pose = transformed_pt.pose
    #         # obs_msg.label = 'bottle'
    #         # self.observation_pub.publish(obs_msg)
    #         rospy.loginfo("Adding {} to planning scene.".format(obj.object.name))
    #         self.scene.add_box(obj.object.name, obj_pose, (obj.object.primitives[0].dimensions[0], obj.object.primitives[0].dimensions[1], obj.object.primitives[0].dimensions[2]))
    #     idx = -1
    #     for surface in find_result.support_surfaces:
    #         if surface.primitive_poses[0].position.z <= 0.25:
    #             continue
    #         idx+=1
    #         surface.name = 'surface_{}'.format(idx)
    #         surface_pose = PoseStamped()
    #         surface_pose.pose = surface.primitive_poses[0]
    #         surface_pose.header.frame_id = 'base_link'
    #         self.scene.add_box(surface.name, surface_pose, (surface.primitives[0].dimensions[0], surface.primitives[0].dimensions[1], surface.primitives[0].dimensions[2]))
    #         self.arm.set_support_surface_name(surface.name)
    
    def grasploc_cb(self, msg):
        self.update_scene()
        rospy.sleep(5)
        self.send_grasps(msg.poses)
        self.scene.clear()
        


        


if __name__ == '__main__':
    rospy.init_node('fetch_pick')
    foo = PlaceClient()
    while not rospy.is_shutdown():
        rospy.spin()
    roscpp_shutdown()
