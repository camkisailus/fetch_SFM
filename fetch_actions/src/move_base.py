#! /usr/bin/python

import actionlib
import rospy
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import Pose2D
from math import sin, cos

class MoveBaseClient(object):
    def __init__(self):
        self.client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        self.goal_sub = rospy.Subscriber("/move_base/to", Pose2D, self.callback)
        rospy.loginfo("Waiting for move_base...")
        self.client.wait_for_server()
    
    def callback(self, msg):
        self.go_to(msg.x, msg.y, msg.theta)
        
    def go_to(self, x, y, theta, frame='map'):
        move_goal = MoveBaseGoal()
        move_goal.target_pose.pose.position.x = x
        move_goal.target_pose.pose.position.y = y
        move_goal.target_pose.pose.orientation.z = sin(theta/2.0)
        move_goal.target_pose.pose.orientation.w = cos(theta/2.0)
        move_goal.target_pose.header.frame_id = frame
        move_goal.target_pose.header.stamp = rospy.Time.now()

        self.client.send_goal(move_goal)
        self.client.wait_for_result()

if __name__ == '__main__':
    rospy.init_node('move_base_client')
    move_base = MoveBaseClient()
    r = rospy.Rate(10)
    while not rospy.is_shutdown():
        r.sleep()