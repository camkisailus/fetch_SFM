#! /usr/bin/python

import rospy
import sys
import actionlib

from moveit_commander import PlanningSceneInterface, roscpp_initialize, roscpp_shutdown, MoveGroupCommander
from geometry_msgs.msg import PoseStamped, PoseArray
from moveit_msgs.msg import Grasp
from trajectory_msgs.msg import JointTrajectoryPoint
from grasping_msgs.msg import FindGraspableObjectsAction, FindGraspableObjectsGoal

class GraspableObject:
    def __init__(self, name, pose):
        self.name = name
        self.pose = pose

class GraspClient:
    def __init__(self):
        roscpp_initialize(sys.argv)
        self.scene = PlanningSceneInterface()
        # self.fetch = RobotCommander()
        self.arm = MoveGroupCommander('arm', wait_for_servers=30)
        self.find_client = actionlib.SimpleActionClient('basic_grasping_perception/find_objects', FindGraspableObjectsAction)
        self.find_client.wait_for_server()
        rospy.sleep(1)
        self.grasploc_sub = rospy.Subscriber('grasploc', PoseArray, self.grasploc_cb)
    
    def update_scene(self):
        goal = FindGraspableObjectsGoal()
        goal.plan_grasps = False
        self.find_client.send_goal(goal)
        self.find_client.wait_for_result()
        find_result = self.find_client.get_result()
        idx = -1
        # rospy.loginfo("Found {} objects".format(len(find_result.objects)))
        self.graspable_objs = []
        for obj in find_result.objects:
            if obj.object.primitive_poses[0].position.z <= 0.6 or obj.object.primitive_poses[0].position.x >= 1.5:
                continue
            # if obj.object.primitive_poses[0].position.x >= 0.8:
            #     # Remove detections that are far
            #     continue
            idx += 1
            obj.object.name = 'object_{}'.format(idx)
            # rospy.loginfo(obj.object)
            obj_pose = PoseStamped()
            obj_pose.pose = obj.object.primitive_poses[0]
            obj_pose.header.frame_id = 'base_link'
            self.graspable_objs.append(GraspableObject(obj.object.name, obj_pose))
            rospy.loginfo("Adding {} to planning scene.".format(obj.object.name))
            self.scene.add_box(obj.object.name, obj_pose, (obj.object.primitives[0].dimensions[0], obj.object.primitives[0].dimensions[1], obj.object.primitives[0].dimensions[2]))
        idx = -1
        for surface in find_result.support_surfaces:
            if surface.primitive_poses[0].position.z <= 0.25:
                continue
            idx+=1
            surface.name = 'surface_{}'.format(idx)
            surface_pose = PoseStamped()
            surface_pose.pose = surface.primitive_poses[0]
            surface_pose.header.frame_id = 'base_link'
            self.scene.add_box(surface.name, surface_pose, (surface.primitives[0].dimensions[0], surface.primitives[0].dimensions[1], surface.primitives[0].dimensions[2]))
            self.arm.set_support_surface_name(surface.name)
    
    def grasploc_cb(self, msg):
        self.update_scene()
        rospy.sleep(5)
        obj_to_grasp = self.graspable_objs[0]
        grasps = []
        for grasp_pose in msg.poses:
            grasp = Grasp()
            grasp.id = 'test'
            grasp.grasp_pose.pose = grasp_pose
            grasp.grasp_pose.header.frame_id = 'base_link'

            grasp.pre_grasp_posture.joint_names = ['r_gripper_finger_joint', 'l_gripper_finger_joint']
            pos = JointTrajectoryPoint()
            pos.positions.append(0.05) # all the way open
            pos.positions.append(0.05)
            pos.time_from_start = rospy.Duration(3)
            grasp.pre_grasp_posture.points.append(pos)

            # set grasp posture
            grasp.grasp_posture.joint_names = ['r_gripper_finger_joint', 'l_gripper_finger_joint']
            pos = JointTrajectoryPoint()
            pos.positions.append(0.0) # close grippers
            pos.positions.append(0.0)
            pos.effort.append(0.0)
            pos.effort.append(0.0)
            grasp.grasp_posture.points.append(pos)

            grasp.pre_grasp_approach.direction.header.frame_id = 'wrist_roll_link'
            grasp.pre_grasp_approach.direction.vector.x = 1.0
            grasp.pre_grasp_approach.min_distance = 0.10
            grasp.pre_grasp_approach.desired_distance = 0.17

            grasp.post_grasp_retreat.direction.header.frame_id = 'base_link'
            grasp.post_grasp_retreat.direction.vector.z = 1.0
            grasp.post_grasp_retreat.min_distance = 0.10
            grasp.post_grasp_retreat.desired_distance = 0.17

            grasp.allowed_touch_objects = [obj_to_grasp.name]
            grasps.append(grasp)
        
        self.arm.pick(obj_to_grasp.name, grasps)


        


if __name__ == '__main__':
    rospy.init_node('fetch_pick')
    foo = GraspClient()
    while not rospy.is_shutdown():
        rospy.spin()
    roscpp_shutdown(sys.argv)
