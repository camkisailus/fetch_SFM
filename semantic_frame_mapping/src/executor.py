#! /usr/bin/python3

import rospy
from particle_filters import *
from utils import *
from fetch_action_client import ActionClient

class Executor():
    def __init__(self, experiment_config=None):
        rospy.logwarn("START INIT EXECUTOR")
        self.ac = ActionClient()
        self.experiment_config = experiment_config
        self.state = State(experiment_config['action_history'])
        rospy.logwarn("INIT EXECUTOR DONE")
    def run_observation_routine(self):
        ## Override in base-class
        pass

    def execute_frame(self, frame_name):
        ## Override in base-class
        pass

