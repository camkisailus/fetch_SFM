#! /usr/bin/python

import rospy
import actionlib
from control_msgs.msg import PointHeadAction, PointHeadGoal
from geometry_msgs.msg import Point

class PointHeadClient(object):
    def __init__(self):
        self.client = actionlib.SimpleActionClient('head_controller/point_head', PointHeadAction)
        self.look_sub = rospy.Subscriber('/point_head/at', Point, self.callback)
        rospy.loginfo("Waiting for head_controller...")
        self.client.wait_for_server()

    def callback(self, msg):
        self.look_at(msg.x, msg.y, msg.z)
        
    def look_at(self, x, y, z, frame='map'):
        goal = PointHeadGoal()
        goal.target.header.stamp = rospy.Time.now()
        goal.target.header.frame_id = frame
        goal.target.point.x = x
        goal.target.point.y = y
        goal.target.point.z = z
        goal.min_duration = rospy.Duration(1.0)
        self.client.send_goal(goal)
        self.client.wait_for_result()

if __name__ == '__main__':
    rospy.init_node('point_head_client')
    point_head = PointHeadClient()
    r = rospy.Rate(10)
    while not rospy.is_shutdown():
        r.sleep()