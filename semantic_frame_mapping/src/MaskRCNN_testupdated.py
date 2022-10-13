#! /home/cuhsailus/anaconda3/envs/maskRcnn/bin/python 
# /usr/bin/python
import random
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
import numpy as np
import cv2
import torchvision.models.segmentation
import torch
import tf
import rospy, geometry_msgs#, tf2_geometry_msgs, tf2_ros
import threading
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError
import ros_numpy

from numpy.linalg import inv
from std_msgs.msg import String, Bool
from semantic_frame_mapping.msg import ObjectDetection, ObjectDetectionArray

#imageSize=[600,600]
#imgPath="Image.jpg"


class NeuralNet(object):
    def __init__(self):
        # self.imgPath = imgPath
        #Loading the net first
        self.device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')   # train on the GPU or on the CPU, if a GPU is not available
        self.model = torchvision.models.detection.maskrcnn_resnet50_fpn(pretrained=True)  # load an instance segmentation model pre-trained pre-trained on COCO
        self.in_features = self.model.roi_heads.box_predictor.cls_score.in_features  # get number of input features for the classifier
        self.model.roi_heads.box_predictor = FastRCNNPredictor(self.in_features,num_classes=19)  # replace the pre-trained head with a new one
        self.model.load_state_dict(torch.load(rospy.get_param("~weights_path")))
        self.model.to(self.device)# move model to the right device
        self.model.eval()
        # self.tfBuffer = tf2_ros.Buffer()
        # self.transform_listener = tf2_ros.TransformListener(self.tfBuffer)
        self.transform_listener = tf.TransformListener()
        #Subscriber
        self.img_msg = rospy.Subscriber(
            "/head_camera/rgb/image_raw",
            Image,
            self.camera_callback,
            queue_size=1)
        self.run_net = rospy.Subscriber(
            "/user/run_detection",
            Bool,
            self.imageto3D,
            queue_size=1
        )
        self.img_depth_msg = rospy.Subscriber(
            "/head_camera/depth_registered/image",
            Image,
            self.camera_depth_callback,
            queue_size=1)
        #Publisher
        self.detection_pub = rospy.Publisher(
            "/scene/observations",
            ObjectDetectionArray,
            queue_size=10
        )
        self.img_pub = rospy.Publisher(
            "/maskRCNN/detections",
            Image,
            queue_size=10
        )
        self.img_msg = rospy.Subscriber(
             "/camera/color/image_rect_color",
             Image,
             self.camera_callback,
             queue_size=1)            
         #self._bridge = CvBridge()
        self._lock = threading.RLock()
        self._image = None
        self.image_depth = None
        # self.imageSize=[600,600]
        # Final pose values
        self.X = 0
        self.Y = 0
        self.Z = 0
        self.thetaX = 0
        self.thetaY = 0
        self.thetaZ = 0
        self.class_labels =  {
            '002_master_chef_can': 1,
            '003_cracker_box': 2,
            '004_sugar_box': 3,
            '005_tomato_soup_can': 4,
            '006_mustard_bottle': 5,
            '007_tuna_fish_can': 6,
            '009_gelatin_box': 8,
            '010_potted_meat_can': 9,
            '025_mug': 14,
            '040_large_marker': 18
        }
        self.inv_class_labels = {label: name for name, label in self.class_labels.items()}

        self.color_labels = {
            1: (100, 100, 100),#(51,107,255),
            2: (0, 0, 0),#(255, 129, 51),
            3: (222, 209, 79),
            4: (0, 0, 255),#(222, 134, 79),
            5: (255, 255, 255),#(255, 237, 51),
            6: (79,152,222),
            8: (218,79,222),
            9: (162,79,222),
            14: (255,0,0),
            18: (0,0,0)
        }

    def camera_callback(self, Img_msg):
        with self._lock:
            try:
                rospy.loginfo_once('Image Received')
                self._image = ros_numpy.numpify(Img_msg) #np.frombuffer(Img_msg.data, dtype=np.uint8).reshape(Img_msg.height, Img_msg.width, -1)
                # self._image = self._bridge.imgmsg_to_cv2(Img_msg, "bgr8")
            except (CvBridgeError, TypeError) as e:
                rospy.logerr(
                    'Could not convert img msg to cv2. Error: {}'.format(e))
                return

    def camera_depth_callback(self, Img_depth_msg):
        with self._lock:
            try:
                rospy.loginfo_once('Depth Received')
                self.image_depth = ros_numpy.numpify(Img_depth_msg)
                # rospy.loginfo(self.image_depth.shape)
                # rospy.loginfo(np.unique(self.image_depth))
            except (CvBridgeError, TypeError) as e:
                rospy.logerr(   
                    'Could not convert img msg to cv2. Error: {}'.format(e))
                return       

    def filter_network(self):
        images = self._image
        # images=cv2.imread(self.imgPath)
        # images = cv2.resize(images, self.imageSize, cv2.INTER_LINEAR)
        images = torch.as_tensor(images, dtype=torch.float32).unsqueeze(0)
        images=images.swapaxes(1, 3).swapaxes(2, 3)
        images = list(image.to(self.device) for image in images)
        return images
    
    def prediction(self):
        with self._lock:
            with torch.no_grad():
                images = self.filter_network()
                pred = self.model(images)
            # box=[]

            im = images[0].swapaxes(0, 2).swapaxes(0, 1).detach().cpu().numpy().astype(np.uint8)
            im2 = im.copy()
            dp_img_cp = self.image_depth.copy()
            detected_classes = []
            box_centroids = []
            for i in range(len(pred[0]['masks'])):
                msk=pred[0]['masks'][i,0].detach().cpu().numpy()
                scr=pred[0]['scores'][i].detach().cpu().numpy()
                
                if scr>0.95:
                    class_label = int(pred[0]['labels'][i].detach().cpu())
                    detected_classes.append(class_label)
                    b, g, r = self.color_labels[int(class_label)]
                    im2[:,:,0][msk>0.95] = r
                    im2[:, :, 1][msk > 0.95] = g
                    im2[:, :, 2][msk > 0.95] = b
                    box = pred[0]['boxes'][i].detach().cpu().numpy()
                    centroidbox_x = (box[0] + box[2])/2
                    centroidbox_y = (box[1] + box[3])/2
                    # cv2.rectangle(img_cp, (xmin, ymin), (xmax, ymax), (r,g,b), 2)
                    cv2.rectangle(im2, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (r,g,b), 2)
                    # cv2.rectangle(dp_img_cp, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (r,g,b), 2)
                    # cv2.imshow(str(scr), np.hstack([im,im2])) #oublis instead of imshow
                    box_centroids.append([centroidbox_x, centroidbox_y])
            # cv2.waitKey()
            # for cls in detected_classes:
            #     rospy.loginfo("Detected {}".format(self.inv_class_labels[cls]))
            self.img_pub.publish(ros_numpy.msgify(Image, im2, encoding="rgb8"))
            # self.d_img_pub.publish(ros_numpy.msgify(Image, dp_img_cp, encoding="uint8"))
            # self.detection_pub.publish()
            return box_centroids
            # return centroidbox_x, centroidbox_y
        
    def imageto3D(self, msg):
        image2D = np.array([])
        #box_3D_centroids=np.array([])
        #MapPoints=np.array([])
        #K = [527.1341414037195, 0.0, 323.8974379222906, 0.0, 525.9099904918304, 227.2282369544078, 0.0, 0.0, 1.0]
        fetchcam_intrinsic = np.array([[527.1341414037195, 0.0, 323.8974379222906], 
                                        [0.0, 525.9099904918304, 227.2282369544078], 
                                        [0.0, 0.0, 1.0]])

        detectionmsg_actual3d = ObjectDetectionArray()#after all conversions
        box_2D_centroids = self.prediction()
        # Zc = self.img_depth.data[0]
        for i in range(len(box_2D_centroids)):
            # rospy.loginfo("Centroid loc: ({})u,v".format(box_2D_centroids[i]))

            # Zc = self.image_depth[int(box_2D_centroids[i][0])][int(box_2D_centroids[i][1])] / 1000
            Zc = self.image_depth[int(box_2D_centroids[i][1])][int(box_2D_centroids[i][0])] / 1000
            rospy.logwarn("Zc = {}".format(Zc))
            image2D = np.array([box_2D_centroids[i][0],box_2D_centroids[i][1], 1])

            image3Dcamera = np.matmul(inv(fetchcam_intrinsic), image2D)
            point2transform_pose = geometry_msgs.msg.PoseStamped()

            point2transform_pose.header.frame_id = 'head_camera_rgb_optical_frame'
            point2transform_pose.header.stamp = rospy.Time.now()

            point2transform_pose.pose.position.x = image3Dcamera[0] * Zc
            point2transform_pose.pose.position.y = image3Dcamera[1] * Zc
            point2transform_pose.pose.position.z = image3Dcamera[2] * Zc
            
            point2transform_pose.pose.orientation.x = 0
            point2transform_pose.pose.orientation.y = 0
            point2transform_pose.pose.orientation.z = 0
            point2transform_pose.pose.orientation.w = 1
            self.transform_listener.waitForTransform("/head_camera_rgb_optical_frame", "/base_link", rospy.Time.now(), rospy.Duration(2.0))
            try:
                # rospy.logwarn(point2transform_pose)
                pose_transformed = self.transform_listener.transformPose('/base_link', point2transform_pose)
            except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException, Exception) as e:
                rospy.loginfo("TF Exception... {}".format(e))
                return  
            
            # detection_actual3d.Point = point_transformed
            # TODO: Add label info to detection_actual3d.label
            detection_actual3d = ObjectDetection()
            detection_actual3d.pose = pose_transformed
            detection_actual3d.label = "foo"
            detectionmsg_actual3d.detections.append(detection_actual3d)
            
        rospy.loginfo(detectionmsg_actual3d)
        self.detection_pub.publish(detectionmsg_actual3d)
        #self.detection_pub.publish(detectionmsg)
        # self.detection_pub.publish(box_3D_centroids)
        
        
        

    # Publish 3D coordinates of all bounding boxes
    """ def messagePublisher(self):
        observation = None
        observation.pose.position.x = self.X
        observation.pose.position.y = self.Y
        observation.pose.position.z = self.Z
        
        msg = "Hello"#f"Hello, the pose is {self.X}, {self.Y}, {self.Z}, and the angle is {self.thetaX}, {self.thetaY}, {self.thetaZ} \n"
        
        message_publisher_string = rospy.Publisher('pose_msg', String, queue_size=10)
        message_publisher = rospy.Publisher('scene/observations', ObjectDetection, queue_size=10)
        
        message_publisher.publish(observation)
        message_publisher_string.publish(msg) """





if __name__ == '__main__':
    rospy.init_node("MaskRCNN_Predictor")
    foo = NeuralNet()
    while not rospy.is_shutdown():
        rospy.spin()
    # try:
        
    # except rospy.ROSInterruptException:
    #     pass


""" Filter_Network- 2 callbacks
Filter_low_probablility_stuff
Project_to_3D
Publish """

""" video_frame_cm_height =
        video_frame_cm_width =
        video_frame_pixel_height =
        video_frame_pixel_width = """ 