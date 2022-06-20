#! /usr/bin/python

import rospy
import actionlib
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.msg import FollowJointTrajectoryAction, FollowJointTrajectoryGoal
from std_msgs.msg import Float32

class TorsoControllerClient(object):
    def __init__(self):
        self.client = actionlib.SimpleActionClient("torso_controller/follow_joint_trajectory", FollowJointTrajectoryAction)
        self.pos_sub = rospy.Subscriber("move_torso/to", Float32, self.callback)
        rospy.loginfo("Waiting for torso_controller")
        self.client.wait_for_server()
        rospy.loginfo("Connected to server ...")
        self.joint_names = ['torso_lift_joint']
    
    def callback(self, msg):
        self.move_to([msg.data])
    
    def move_to(self, position):
        traj = JointTrajectory()
        traj.joint_names = self.joint_names
        traj.points.append(JointTrajectoryPoint())
        traj.points[0].positions = position
        traj.points[0].velocities = [0.0]
        traj.points[0].accelerations = [0.0]
        traj.points[0].time_from_start = rospy.Duration(5.0)
        follow_goal = FollowJointTrajectoryGoal()
        follow_goal.trajectory = traj
        self.client.send_goal(follow_goal)
        self.client.wait_for_result()

if __name__ == '__main__':
    rospy.init_node('torso_client')
    torso_action = TorsoControllerClient()
    r = rospy.Rate(10)
    while not rospy.is_shutdown():
        r.sleep()