import glob
import yaml

"""
Collab Table
    stamp: 
    secs: 1675738607
    nsecs: 669347763
    frame_id: "map"
    pose: 
    pose: 
        position: 
        x: -17.8292420874
        y: 9.85325426182
        z: 0.0
        orientation: 
        x: 0.0
        y: 0.0
        z: 0.25064314552
        w: 0.968079549213
Light Circle Table
    stamp: 
    secs: 1675738738
    nsecs: 743212223
    frame_id: "map"
    pose: 
    pose: 
        position: 
        x: -8.96643690381
        y: 2.81309229639
        z: 0.0
        orientation: 
        x: 0.0
        y: 0.0
        z: 0.229088603621
        w: 0.973405574101
Dark Circle Table
    stamp: 
    secs: 1675738847
    nsecs: 880622387
    frame_id: "map"
    pose: 
    pose: 
        position: 
        x: -5.34470155007
        y: -1.1161882333
        z: 0.0
        orientation: 
        x: 0.0
        y: 0.0
        z: 0.829094923009
        w: 0.559107868519
Bar Table
    stamp: 
    secs: 1675738950
    nsecs: 486177444
    frame_id: "map"
    pose: 
    pose: 
        position: 
        x: -4.73178071852
        y: -2.33222722242
        z: 0.0
        orientation: 
        x: 0.0
        y: 0.0
        z: -0.472783067828
        w: 0.881178852887
"""


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