#! /usr/bin/python

from random import random
import rospy
import numpy as np
import copy
import math
import actionlib
# import tf

from scipy.stats import multivariate_normal
from sklearn.mixture import GaussianMixture
from std_msgs.msg import Bool
from threading import RLock

from visualization_msgs.msg import Marker, MarkerArray
from geometry_msgs.msg import Pose, PointStamped
from std_msgs.msg import Bool
from apriltag_ros.msg import AprilTagDetectionArray

class State():
    def __init__(self):
        self.action_history = ['idle']

class StaticObject(object):
    def __init__(self, label, x, y, z):
        # tf_listener = tf.TransformListener()
        self.label = label
        self.full_name = label
        self.x = x
        self.y = y
        self.z = z
        rospy.loginfo("Observation of {} at ({}, {}, {})".format(self.label, self.x, self.y, self.z))
        self.marker_pub = rospy.Publisher('/filter/static_object/{}'.format(label), MarkerArray, queue_size=10)

        self.marker_array = MarkerArray()
        self.marker = Marker()

        self.marker.header.frame_id = 'map'
        self.marker.id = 0
        self.marker.type = self.marker.CUBE
        self.marker.action = self.marker.ADD
        self.marker.scale.x = 0.2
        self.marker.scale.y = 0.2
        self.marker.scale.z = 0.2
        # self.marker.color.b = 1
        self.marker.color.a = 1
        self.marker.pose.orientation.w = 1.0
        self.marker.pose.position.x = self.x
        self.marker.pose.position.y = self.y
        self.marker.pose.position.z = self.z

        self.marker_array.markers.append(self.marker)

    def publish(self):
        self.marker_pub.publish(self.marker_array)

class ParticleFilter(object):
    def __init__(self, n, label, valid_regions):
        self.n = n
        self.Sigma = np.array([[0.02, 0, 0], [0, 0.02, 0], [0, 0, 0.02]])
        self.particles = np.zeros([n,3])
        self.weights = 1.0/self.n * np.ones([n])
        if len(valid_regions) == 0:
            self.valid_regions = [region_id for region_id in REGIONS.keys()]
        else:
            self.valid_regions = [region_id for region_id in valid_regions]
        self.reinvigoration_idx = 0
        self.label = label
        self.marker_pub = rospy.Publisher('filters/{}'.format(label), MarkerArray, queue_size=10)
        for i in range(self.n):
            self.particles[i] = self.reinvigorate(self.particles[i])
        
    def reinvigorate(self, particle):
        region = self.valid_regions[self.reinvigoration_idx % len(self.valid_regions)]
        min_x, max_x, min_y, max_y = REGIONS[region]
        particle[0] = min_x + np.random.random()*(max_x - min_x)
        particle[1] = min_y + np.random.random()*(max_y - min_y)
        particle[2] = 0.5
        self.reinvigoration_idx+=1

        return particle

    def systematic_resample(self):
        """ Performs the systemic resampling algorithm used by particle filters.

        This algorithm separates the sample space into N divisions. A single random
        offset is used to to choose where to sample from for all divisions. This
        guarantees that every sample is exactly 1/N apart.

        Parameters
        ----------
        weights : list-like of float
            list of weights as floats

        Returns
        -------

        indexes : ndarray of ints
            array of indexes into the weights defining the resample. i.e. the
            index of the zeroth resample is indexes[0], etc.
        """
        N = len(self.weights)

        # make N subdivisions, and choose positions with a consistent random offset
        positions = (np.random.random() + np.arange(N)) / N

        indexes = np.zeros(N, 'i')
        cumulative_sum = np.cumsum(self.weights)
        i, j = 0, 0
        while i < N:
            if positions[i] < cumulative_sum[j]:
                indexes[i] = j
                i += 1
            else:
                j += 1
        return indexes
    
    def resample(self):
        # Low Variance Resampling
        # particles_added = 0
        # temp_p = np.zeros([self.n, 3])
        # w = np.cumsum(self.weights)
        # r = np.random.rand(1) / self.n
        # j = 1
        # for i in range(self.n):
        #     u = r + (i-1) / self.n
        #     while u > w[j]:
        #         j += 1
        #     temp_p[i] = self.particles[j]
        #     particles_added +=1
        #     if particles_added > self.n*0.9:
        #         break
        # for i in range(particles_added, self.n):
        #     temp_p[i] = self.reinvigorate()
        # self.particles = copy.deepcopy(temp_p)
        # self.weights = 1/self.n * np.ones([self.n])

        draw = np.random.choice(self.n, int(self.n*0.8), p=self.weights, replace=True)
        temp_p = self.particles[:]
        temp_w = self.weights[:]
        self.particles[0, :] = copy.deepcopy(temp_p[np.argmax(self.weights)])
        self.weights[0] = copy.deepcopy(temp_w[np.argmax(self.weights)])
        self.particles[1, :] = self.jitter(copy.deepcopy(temp_p[np.argmax(self.weights)]))
        self.weights[1] = copy.deepcopy(temp_w[np.argmax(self.weights)])
        for i in range(len(draw)):
            self.particles[i+2] = copy.deepcopy(temp_p[draw[i]])
            self.weights[i+2] = copy.deepcopy(temp_w[draw[i]])

        for j in range(2+len(draw), self.n):
            self.particles[j] = self.reinvigorate(self.particles[j])
            self.weights[j] = 1/self.n
    
    def jitter(self, particle):
        x_noise = np.random.normal(0, self.Sigma[0,0])
        y_noise = np.random.normal(0, self.Sigma[1,1])
        z_noise = np.random.normal(0, self.Sigma[2,2])
        particle[0] += x_noise
        particle[1] += y_noise
        particle[2] += z_noise
        return particle

    def update_filter(self):
        for k in range(self.n):
            self.particles[k, :]= self.jitter(self.particles[k, :])
            self.weights[k] = self.assign_weight(self.particles[k, :])
        # try annealing
        self.weights = self.weights / np.sum(self.weights)
        self.resample()
    
    def publish(self):
        marker_array = MarkerArray()
        highest_weight = max(self.weights)
        lowest_weight = min(self.weights)
        threshold = lowest_weight + float((highest_weight-lowest_weight)*0.9)
        for i in range(self.n):
            marker = Marker()
            marker.id = i
            marker.header.frame_id = 'map'
            if self.label == 'grasp_spoon':
                marker.color.r = 1
                marker.type = marker.SPHERE
            elif self.label == 'grasp_mug':
                marker.color.b = 1
                marker.type = marker.SPHERE
            elif self.label == 'stir_mug':
                marker.color.r = 0.5
                marker.color.b = 0.5
                marker.type = marker.CUBE
            elif self.label == 'spoon':
                marker.color.r = 1
                marker.type = marker.CUBE
            elif self.label == 'mug':
                marker.color.b = 1
                marker.type = marker.CUBE
            
            marker.action = marker.ADD
            marker.scale.x = 0.2
            marker.scale.y = 0.2
            marker.scale.z = 0.2
            if self.weights[i] < threshold:
                marker.color.a = 0.1
            else:
                marker.color.a = 1.0
            marker.pose.orientation.w = 1.0
            marker.pose.position.x = self.particles[i, 0]
            marker.pose.position.y = self.particles[i, 1]
            marker.pose.position.z = self.particles[i, 2]
            marker_array.markers.append(marker)
        self.marker_pub.publish(marker_array)

class ObjectParticleFilter(ParticleFilter):
    def __init__(self, n, valid_regions, label):
        super(ObjectParticleFilter, self).__init__(n, label, valid_regions)
        self.ar_to_obj_map = {0: 'mug'}
        self.observation_sub = rospy.Subscriber('scene/observations', Pose, self.add_observation, queue_size=1)
        self.apriltag_sub = rospy.Subscriber('tag_detections', AprilTagDetectionArray, self.handle_ar_detection, queue_size=1)
        
        self.marker_pub = rospy.Publisher('filter/particles/{}'.format(label), MarkerArray, queue_size=10)
        self.observations = []
        # if self.label == 'spoon':
        #     dummy_obs = StaticObject('spoon', -0.482136274403, 2.11895497563, 0.798618733883)
        #     self.observations.append(dummy_obs)
        # elif self.label == 'mug':
        #     dummy_obs = StaticObject('mug', 2.48213674403, 2.11895497563, 0.798618733883 )
        #     other_mug = StaticObject('mug_2', 8.5, -4.0, 0.798618733883)
        #     self.observations.append(other_mug)
        #     self.observations.append(dummy_obs)
    
    def handle_ar_detection(self, msg):
        # rospy.loginfo("Got AR tag detection")
        for detection in msg.detections:
            if(len(self.observations) > 0):
                return
            obj_label = self.ar_to_obj_map[detection.id[0]]
            if obj_label == self.label:
                pt = PointStamped()
                pt.header.frame_id = detection.pose.header.frame_id
                pt.point.x = detection.pose.pose.pose.position.x
                pt.point.y = detection.pose.pose.pose.position.y
                pt.point.z = detection.pose.pose.pose.position.z
                # transformed_pt = tf_listener.transformPoint('map', pt)
                obj = StaticObject(obj_label, transformed_pt.point.x, transformed_pt.point.y, transformed_pt.point.z)
                print("Adding observation: {} to filter: {}".format(obj.label, self.label))
                self.observations.append(obj)
            
        
    def add_observation(self, observation):
        if self.label == 'spoon':
            rospy.loginfo("Received observation at ({}, {}, {})".format(observation.position.x, observation.position.y, observation.position.z))
            obj = StaticObject('spoon', observation.position.x, observation.position.y, observation.position.z)
            self.observations.append(obj)
    
    
    def assign_weight(self, particle):
        if len(self.observations) == 0:
            return 1
        for i, observation in enumerate(self.observations):
            err_x = particle[0] - observation.x
            err_y = particle[1] - observation.y
            err_z = particle[2] - observation.z
            dist = math.sqrt(err_x**2 + err_y**2 + err_z**2)
            phi = math.exp(-1 * dist)
            if i == 0:
                max_phi = phi
            else:
                max_phi = max(max_phi, phi)
        return max_phi

    def update_filter(self):
        for k in range(self.n):
            self.particles[k, :]= self.jitter(self.particles[k, :])
            self.weights[k] = self.assign_weight(self.particles[k, :])
        # try annealing
        self.weights = self.weights / np.sum(self.weights)
        self.resample()
           
class FrameParticleFilter(ParticleFilter):
    def __init__(self, n, label, preconditions, core_frame_elements, valid_regions):
        super(FrameParticleFilter, self).__init__(n, label, valid_regions)
        self.lock = RLock()
        self.marker_pub = rospy.Publisher('filter/particles/{}'.format(label), MarkerArray, queue_size=10)
        self.execute_sub = rospy.Subscriber('{}/execute'.format(self.label), Bool, self.execute, queue_size=1)
        self.frame_element_filters = {frame_element:None for frame_element in core_frame_elements}
        self.frame_elements = core_frame_elements
        if preconditions:
            self.precondition_filters = {precondition:None for precondition in preconditions}
            self.preconditions = preconditions
            self.next_precondition = preconditions[0]
        else:
            self.preconditions = None
    
    def execute(self, msg):
        # get gmm
        mean, _ = self.gmm()
        nav_goal_x = mean[0] - 1.5
        nav_goal_y = mean[1]
        nav_goal_t = 0.0
        rospy.loginfo("Navigating to ({}, {}, {})".format(nav_goal_x, nav_goal_y, nav_goal_t))
        move_base.go_to(nav_goal_x, nav_goal_y, nav_goal_t)
        head_action.look_at(mean[0], mean[1], mean[2])
        mean, _ = self.gmm()
        nav_goal_x = mean[0] - 0.8
        nav_goal_y = mean[1]
        nav_goal_t = 0.0
        rospy.loginfo("Navigating to ({}, {}, {})".format(nav_goal_x, nav_goal_y, nav_goal_t))
        move_base.go_to(nav_goal_x, nav_goal_y, nav_goal_t)
        # torso_action.move_to([0.35])
        grasping_client.updateScene()
        cube, grasps = grasping_client.getGraspableCube()
        if cube == None:
            rospy.logwarn("No graspable objects in scene")
        else:
            # rospy.loginfo(type(grasps))
            grasping_client.pick(cube, grasps)
            grasping_client.tuck()
        # torso_action.move_to([0.2])

        # # TODO: Change this to be Actionlib calls for each SF
        # if self.label == 'grasp_spoon':
        #     rospy.loginfo("Go to ({:.4f}, {:.4f}, {:.4f}".format(mean[0]+1.3, mean[1], math.pi))
        #     move_base.go_to(mean[0]+1.3, mean[1], math.pi, 'map')
        #     rospy.loginfo("Raising torso to {:.4f}".format(0.4))
        #     torso_action.move_to([0.4])
        #     rospy.loginfo("Look at ({:.4f}, {:.4f}, {:.4f})".format(mean[0], mean[1], mean[2]))
        #     head_action.look_at(mean[0], mean[1], mean[2], 'map')
        #     grasping_client.updateScene()
        #     cube, grasps = grasping_client.getGraspableCube()
            # if cube == None:
            #     # perception failed
            #     rospy.logwarn("perception failed")
            # else:
            #     grasping_client.publish_observation(cube)
            #     grasping_client.pick(cube, grasps)
            #     grasping_client.tuck()
        #     move_base.go_to(0, 0, 0, 'map')
        # elif self.label == 'stir_mug':
        #     move_base.go_to(mean[0]+1.15, mean[1], math.pi, 'map')
        #     torso_action.move_to([.4])
        #     head_action.look_at(mean[0], mean[1], mean[2], 'map')
        #     grasping_client.updateScene()
        #     cube, grasps = grasping_client.getGraspableCube()
        #     if cube == None:
        #         # perception failed
        #         rospy.logwarn("perception failed")
        #     else:
        #         grasping_client.publish_observation(cube)
        #         grasping_client.pick(cube, grasps)
        #         grasping_client.tuck()
        #     state.action_history = ['grasp_spoon']            
        #     rospy.sleep(rospy.Duration(5.0))
        #     mean, _ = self.gmm()
        #     move_base.go_to(mean[0], mean[1]+1.0, -float(math.pi/2.0), 'map')
        #     torso_action.move_to([.4])
        #     head_action.look_at(mean[0], mean[1], mean[2], 'map')




    
    def gmm(self):
        with self.lock:
            good_particles = []
            max_weight = max(self.weights)
            min_weight = min(self.weights)
            threshold = min_weight + float((max_weight - min_weight)*0.9)
            for i in range(self.n):
                if self.weights[i] >=threshold:
                    good_particles.append(self.particles[i,:])
            gm = GaussianMixture(random_state=0).fit(good_particles)
            return  gm.means_[0], gm.covariances_
            
    def add_frame_element(self, frame_element_filter, frame_element_name):
        self.frame_element_filters[frame_element_name] = frame_element_filter
    
    def add_precondition(self, p_filter, p_name):
        self.precondition_filters[p_name] = p_filter

    # def reinvigorate(self, particle):
    #     region = self.valid_regions[self.reinvigoration_idx % len(self.valid_regions)]
    #     min_x, max_x, min_y, max_y = REGIONS[region]
    #     particle[0] = min_x + np.random.random()*(max_x - min_x)
    #     particle[1] = min_y + np.random.random()*(max_y - min_y)
    #     particle[2] = 1.0
    #     self.reinvigoration_idx+=1

    #     return particle
    
    # def resample(self):
    #     draw = np.random.choice(self.n, int(self.n*0.8), p=self.weights, replace=True)
    #     temp_p = self.particles[:]
    #     temp_w = self.weights[:]
    #     self.particles[0, :] = copy.deepcopy(temp_p[np.argmax(self.weights)])
    #     self.weights[0] = copy.deepcopy(temp_w[np.argmax(self.weights)])
    #     self.particles[1, :] = self.jitter(copy.deepcopy(temp_p[np.argmax(self.weights)]))
    #     self.weights[1] = copy.deepcopy(temp_w[np.argmax(self.weights)])
    #     for i in range(len(draw)):
    #         self.particles[i+2] = copy.deepcopy(temp_p[draw[i]])
    #         self.weights[i+2] = copy.deepcopy(temp_w[draw[i]])

    #     for j in range(2+len(draw), self.n):
    #         self.particles[j] = self.reinvigorate(self.particles[j])
    #         self.weights[j] = 1/self.n
    
    def context_potential(self, particle, state):
        i = 0
        if self.preconditions:
            for precondition in self.preconditions:
                if precondition in state.action_history:
                    i += 1
                else:
                    break
            weight = 1
            while i < len(self.preconditions):
                subtask_filter = self.precondition_filters[self.preconditions[i]]
                for j in range(subtask_filter.n):
                    other_particle = subtask_filter.particles[j, :]
                    dist = np.sqrt((other_particle[0]-particle[0])**2 + (other_particle[1]-particle[1])**2 + (other_particle[2]-particle[2])**2)
                    phi = math.exp(-5*dist)
                    if phi > 0.2:
                        weight += float(1.0/2**i)* subtask_filter.weights[j]
                i+=1
            return weight
        else:
            return 1
    
    def measurement_potential(self, particle, state):
        # determine state wrt preconditions
        i = 0
        if self.preconditions:
            for precondition in self.preconditions:
                if precondition not in state.action_history:
                    break
                else:
                    i+=1
        potential = 0
        core_elem_weight_mod = 1
        while i < len(self.frame_elements):
            core_element_filter = self.frame_element_filters[self.frame_elements[i]]
            for j in range(core_element_filter.n):
                other_particle = core_element_filter.particles[j, :]
                dist = np.sqrt((other_particle[0]-particle[0])**2 + (other_particle[1]-particle[1])**2 + (other_particle[2]-particle[2])**2)
                phi = math.exp(-1*dist)
                potential += (1/math.pow(core_elem_weight_mod,2))*(phi*core_element_filter.weights[j])
            i+=1
            core_elem_weight_mod+=1
        return potential

    def assign_weight(self, particle, state):
        measurement = self.measurement_potential(particle, state)
        # context = self.context_potential(particle, state)
        # rospy.loginfo(self.label)
        # rospy.loginfo("measurement: {:.4f} context: {:.4f}".format(measurement, context))
        return measurement #*context
    
    def update_filter(self, state):
        # rospy.loginfo(state.action_history)
        with self.lock:
            for k in range(self.n):
                self.particles[k, :] = self.jitter(self.particles[k,:])
                self.weights[k] = self.assign_weight(self.particles[k,:], state)
            self.weights = self.weights / np.sum(self.weights)
            self.resample()
            