#!/usr/bin/env python

import rospy
from grasploc_wrapper.srv import GrasplocSrv
from sensor_msgs.msg import PointCloud2


def callback(msg):
    print 'Got a new pointcloud'
    try:
        client = rospy.ServiceProxy('grasploc_srv', GrasplocSrv)
        response = client(msg)
        print response
    except rospy.ServiceException, e:
        print "Service call failed: %s" % e


if __name__ == "__main__":
    rospy.init_node('test')

    print 'listening to /head_camera/depth/points'
    rospy.Subscriber("/head_camera/depth/points", PointCloud2, callback)
    print 'Waiting for grasploc_srv'
    rospy.wait_for_service('grasploc_srv')

    print 'Spining'
    rospy.spin()
