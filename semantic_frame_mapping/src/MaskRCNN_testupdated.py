import random
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
import numpy as np
import cv2
import torchvision.models.segmentation
import torch

import rospy
import threading
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError

from std_msgs.msg import String
from semantic_frame_mapping.msg import ObjectDetection

#imageSize=[600,600]
#imgPath="Image.jpg"

""" device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')   # train on the GPU or on the CPU, if a GPU is not available
model = torchvision.models.detection.maskrcnn_resnet50_fpn(pretrained=True)  # load an instance segmentation model pre-trained pre-trained on COCO
in_features = model.roi_heads.box_predictor.cls_score.in_features  # get number of input features for the classifier
model.roi_heads.box_predictor = FastRCNNPredictor(in_features,num_classes=2)  # replace the pre-trained head with a new one
model.load_state_dict(torch.load("10000.torch"))
model.to(device)# move model to the right device
model.eval() """




class NeuralNet(object):
    def __init__(self, imgPath):
        # self.imgPath = imgPath
        #Loading the net first
        self.device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')   # train on the GPU or on the CPU, if a GPU is not available
        self.model = torchvision.models.detection.maskrcnn_resnet50_fpn(pretrained=True)  # load an instance segmentation model pre-trained pre-trained on COCO
        self.in_features = self.model.roi_heads.box_predictor.cls_score.in_features  # get number of input features for the classifier
        self.model.roi_heads.box_predictor = FastRCNNPredictor(self.in_features,num_classes=2)  # replace the pre-trained head with a new one
        self.model.load_state_dict(torch.load("10000.torch"))
        self.model.to(self.device)# move model to the right device
        self.model.eval()

        #Subscriber
        self.img_msg = rospy.Subscriber(
            "/camera/color/image_raw",
            Image,
            self.camera_callback,
            queue_size=1)
        self.img_msg = rospy.Subscriber(
            "/camera/color/image_raw",
            Image,
            self.camera_callback,
            queue_size=1)            
        self._bridge = CvBridge()
        self._lock = threading.RLock()
        self._image = None
        self.imageSize=[600,600]
        # Final pose values
        self.X = 0
        self.Y = 0
        self.Z = 0
        self.thetaX = 0
        self.thetaY = 0
        self.thetaZ = 0

    def camera_callback(self, Img_msg):
        with self._lock:
            try:
                rospy.loginfo('Image Received')
                self._image = self._bridge.imgmsg_to_cv2(Img_msg, "bgr8")
            except (CvBridgeError, TypeError) as e:
                rospy.logerr(
                    'Could not convert img msg to cv2. Error: {}'.format(e))
                return

    def filter_network(self):
        images = self._image
        # images=cv2.imread(self.imgPath)
        images = cv2.resize(images, self.imageSize, cv2.INTER_LINEAR)
        images = torch.as_tensor(images, dtype=torch.float32).unsqueeze(0)
        images=images.swapaxes(1, 3).swapaxes(2, 3)
        images = list(image.to(device) for image in images)
        return images
    
    def prediction(self):
        with torch.no_grad():
            images = self.filter_network()
            pred = model(images)
        box=[]
        im = images[0].swapaxes(0, 2).swapaxes(0, 1).detach().cpu().numpy().astype(np.uint8)
        im2 = im.copy()
        for i in range(len(pred[0]['masks'])):
            msk=pred[0]['masks'][i,0].detach().cpu().numpy()
            scr=pred[0]['scores'][i].detach().cpu().numpy()
            
            if scr>0.8 :
                im2[:,:,0][msk>0.5] = random.randint(0,255)
                im2[:, :, 1][msk > 0.5] = random.randint(0,255)
                im2[:, :, 2][msk > 0.5] = random.randint(0, 255)
        
        box = pred[0]['boxes'].detach().cpu().numpy()
        centroidbox_x = (box[0][0] + box[0][2])/2
        centroidbox_y = (box[0][1] + box[0][3])/2
        
        cv2.imshow(str(scr), np.hstack([im,im2])) #oublis instead of imshow
        cv2.waitKey()
        return centroidbox_x, centroidbox_y
        
    def imageto3D(self):
        fetchcam_intrinsic = []
        K = [527.1341414037195, 0.0, 323.8974379222906, 0.0, 525.9099904918304, 227.2282369544078, 0.0, 0.0, 1.0]
        fetchcam_extrinsic = np.array([[527.1341414037195, 0.0, 323.8974379222906], 
                                        [0.0, 525.9099904918304, 227.2282369544078], 
                                        [0.0, 0.0, 1.0]])
        #fetchcam_extrinsic_rotation = fetchcam_extrinsic[0:3,0:3]
        #fetchcam_extrinsic_translation = fetchcam_extrinsic[:,3]
        image2D = self.prediction()
        """ video_frame_cm_height =
        video_frame_cm_width =
        video_frame_pixel_height =
        video_frame_pixel_width = """ 

        image3Dcamera = image2D*inv(fetchcam_intrinsic)

        

    # call function at the very end
    def messagePublisher(self):
        observation = None
        observation.pose.position.x = self.X
        observation.pose.position.y = self.Y
        observation.pose.position.z = self.Z
        
        msg = f"Hello, the pose is {self.X}, {self.Y}, {self.Z}, and the angle is {self.thetaX}, {self.thetaY}, {self.thetaZ} \n"
        
        message_publisher_string = rospy.Publisher('pose_msg', String, queue_size=10)
        message_publisher = rospy.Publisher('scene/observations', ObjectDetection, queue_size=10)
        
        message_publisher.publish(observation)
        message_publisher_string.publish(msg)





if __name__ == '__main__':
    try:
        
    except rospy.ROSInterruptException:
        pass


""" Filter_Network- 2 callbacks
Filter_low_probablility_stuff
Project_to_3D
Publish """