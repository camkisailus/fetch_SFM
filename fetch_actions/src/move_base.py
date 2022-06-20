#! /usr/bin/python

import actionlib
import rospy
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import Pose2D
from math import sin, cos
from fetch_actions.msg import MoveBaseRequestAction

class MoveBase(object):
    def __init__(self):
        self.server = actionlib.SimpleActionServer("kisailus_move_base", MoveBaseRequestAction, self.callback, auto_start=False)
        self.server.start()
        self.client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        self.goal_sub = rospy.Subscriber("/move_base/to", Pose2D, self.callback)
        rospy.loginfo("MOVE BASE: Waiting for move_base...")
        self.client.wait_for_server()
        rospy.loginfo("MOVE BASE: Connected to move_base!")
    
    def callback(self, msg):
        rospy.loginfo("MOVE BASE: Received request: {}".format(msg))
        self.go_to(msg.x, msg.y, msg.theta)
        rospy.loginfo("MOVE BASE: Returned from go_to()")
        self.server.set_succeeded()
        
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
        return self.client.get_result()

if __name__ == '__main__':
    rospy.init_node('move_base_client')
    move_base = MoveBase()
    r = rospy.Rate(10)
    while not rospy.is_shutdown():
        r.sleep()