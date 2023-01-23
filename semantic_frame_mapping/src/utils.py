import glob
import yaml
import rospy
from std_msgs.msg import String
from geometry_msgs.msg import PoseWithCovarianceStamped, Pose
from visualization_msgs.msg import Marker

class Frame():
    def __init__(self, info_dict):
        self.name = info_dict['name']
        self.description = info_dict['description']
        self.core_frame_elements = []
        self.optional_frame_elements = []
        for frame_element in info_dict['frame_elements']:
            if frame_element['is_core']:
                self.core_frame_elements.append(frame_element['name'])
            else:
                self.optional_frame_elements.append(frame_element['name'])
        self.preconditions = []
        try:
            preconditions = info_dict['preconditions']
            for precondition in preconditions:
                self.preconditions.append(precondition['name'])
        except KeyError:
            pass

def init_knowledge_base(path, frames):
    knowledge_base = []
    for frame in frames:
        a = path+frame+"_sf.yaml"
        print("Path is {}".format(a))
        with open(path+frame+"_sf.yaml", 'r') as fstream:
            try:
                info_dict = yaml.safe_load(fstream)
                knowledge_base.append(Frame(info_dict))
            except yaml.YAMLError as e:
                print(e)
    return knowledge_base 


class State():
    def __init__(self, action_history=[]):
        self.action_history = action_history
        self.ah_sub = rospy.Subscriber("/add_action_to_action_history", String, self.add_action_to_action_history)
        self.robot_pose_sub = rospy.Subscriber("/amcl_pose", PoseWithCovarianceStamped, self.update_pose)
        self.pose = Pose()

    def update_pose(self, pose_msg):
        self.pose = pose_msg.pose.pose
    
    def add_action_to_action_history(self, action_taken):
        try:
            self.action_history.append(action_taken.data)
        except AttributeError:
            self.action_history.append(action_taken)

class Region():
    def __init__(self, name, min_x, max_x, min_y, max_y, min_z, max_z):
        self.name = name
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.min_z = min_z
        self.max_z = max_z
        self.pub = rospy.Publisher("/region/{}".format(name), Marker, queue_size=1)
        self.marker = Marker()
        self.marker.id = 0
        self.marker.header.frame_id = 'map'
        if name.startswith("neg"):
            self.marker.color.r = 1
        
        self.marker.color.a = 0.5
        self.marker.type = Marker.CUBE
        self.marker.action = Marker.ADD
        self.marker.lifetime = rospy.Duration(0)
        self.marker.pose.position.x = (min_x + max_x)/2
        self.marker.pose.position.y = (min_y + max_y)/2
        self.marker.pose.position.z = (min_z + max_z)/2
        self.marker.pose.orientation.w = 1.0
        self.marker.scale.x = max_x - min_x
        self.marker.scale.y = max_y - min_y
        self.marker.scale.z = max_z - min_z
        self.pub.publish(self.marker)
    
    def __hash__(self):
        return hash(self.name)

    def publish(self):
        self.pub.publish(self.marker)        
    
    def get_bounds(self):
        return (self.min_x, self.max_x, self.min_y, self.max_y, self.min_z, self.max_z)
