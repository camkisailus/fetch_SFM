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
import ros_numpy
import argparse
import time
import torch.backends.cudnn as cudnn
from numpy import random
from pathlib import Path
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError
from numpy.linalg import inv
from std_msgs.msg import String, Bool
from semantic_frame_mapping.msg import ObjectDetection, ObjectDetectionArray

from yolo.yolov7.models.experimental import attempt_load
from yolo.yolov7.utils.datasets import LoadStreams, LoadImages
from yolo.yolov7.utils.general import check_img_size, check_requirements, check_imshow, non_max_suppression, apply_classifier, \
    scale_coords, xyxy2xywh, strip_optimizer, set_logging, increment_path
from yolo.yolov7.utils.plots import plot_one_box
from yolo.yolov7.utils.torch_utils import select_device, load_classifier, time_synchronized, TracedModel


class NeuralNet(object):
    def __init__(self, opt):
        self.source, self.weights, self.view_img = opt.source, opt.weights, opt.view_img
        self.save_txt, self.imgsz, self.trace = opt.save_txt, opt.img_size, not opt.no_trace
        self.save_img = not opt.nosave and not self.source.endswith('.txt')  # save inference images
        self.webcam = self.source.isnumeric() or self.source.endswith('.txt') or self.source.lower().startswith(
            ('rtsp://', 'rtmp://', 'http://', 'https://'))

        self.opt_update = opt.update
        self.opt_augment = opt.augment
        self.opt_conf_thres = opt.conf_thres
        self.opt_iou_thres = opt.iou_thres
        self.opt_classes = opt.classes
        self.opt_agnostic_nms = opt.agnostic_nms

        # Directories
        self.save_dir = Path(increment_path(Path(opt.project) / opt.name, exist_ok=opt.exist_ok))  # increment run
        (self.save_dir / 'labels' if self.save_txt else self.save_dir).mkdir(parents=True, exist_ok=True)  # make dir
        # Initialize
        set_logging()
        self.device = select_device(opt.device)
        self.half = self.device.type != 'cpu'  # half precision only supported on CUDA

        # Load model
        self.model = attempt_load(self.weights, map_location=self.device)  # load FP32 model
        stride = int(self.model.stride.max())  # model stride
        self.imgsz = check_img_size(self.imgsz, s=stride)  # check img_size

        if self.trace:
            self.model = TracedModel(self.model, self.device, opt.img_size)

        if self.half:
            self.model.half()  # to FP16

        self.classify = False
        if self.classify:
            self.modelc = load_classifier(name='resnet101', n=2)  # initialize
            self.modelc.load_state_dict(torch.load('weights/resnet101.pt', map_location=device)['model']).to(device).eval()

        # Set Dataloader
        vid_path, vid_writer = None, None
        if self.webcam:
            view_img = check_imshow()
            cudnn.benchmark = True  # set True to speed up constant image size inference
            self.dataset = LoadStreams(self.source, img_size=self.imgsz, stride=stride)
        else:
            self.dataset = LoadImages(self.source, img_size=self.imgsz, stride=stride)

        
        # Get names and colors
        self.names = self.model.module.names if hasattr(self.model, 'module') else self.model.names
        self.colors = [[random.randint(0, 255) for _ in range(3)] for _ in self.names]



        #tf listener
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
    
    def detect(self):
        box_centroids = []
        labels = []
        # Run inference
        if self.device.type != 'cpu':
            self.model(torch.zeros(1, 3, self.imgsz, self.imgsz).to(self.device).type_as(next(self.model.parameters())))  # run once
        old_img_w = old_img_h = self.imgsz
        old_img_b = 1    

        t0 = time.time()
        for path, img, im0s, vid_cap in self.dataset:
            img = torch.from_numpy(img).to(self.device)
            img = img.half() if self.half else img.float()  # uint8 to fp16/32
            img /= 255.0  # 0 - 255 to 0.0 - 1.0
            if img.ndimension() == 3:
                img = img.unsqueeze(0)

            # Warmup        
            if self.device.type != 'cpu' and (old_img_b != img.shape[0] or old_img_h != img.shape[2] or old_img_w != img.shape[3]):
                old_img_b = img.shape[0]
                old_img_h = img.shape[2]
                old_img_w = img.shape[3]
                for i in range(3):
                    self.model(img, augment=self.opt_augment)[0]

            # Inference
            t1 = time_synchronized()
            with torch.no_grad():   # Calculating gradients would cause a GPU memory leak
                pred = self.model(img, augment=self.opt_augment)[0]
            t2 = time_synchronized()
            
            # Apply NMS
            pred = non_max_suppression(pred, self.opt_conf_thres, self.opt_iou_thres, classes=self.opt_classes, agnostic=self.opt_agnostic_nms)
            t3 = time_synchronized()

            # Apply Classifier
            if self.classify:
                pred = apply_classifier(pred, self.modelc, img, im0s)

            # Process detections
            for i, det in enumerate(pred):  # detections per image
                if self.webcam:  # batch_size >= 1
                    p, s, im0, frame = path[i], '%g: ' % i, im0s[i].copy(), self.dataset.count
                else:
                    p, s, im0, frame = path, '', im0s, getattr(self.dataset, 'frame', 0)

                p = Path(p)  # to Path
                save_path = str(self.save_dir / p.name)  # img.jpg
                txt_path = str(self.save_dir / 'labels' / p.stem) + ('' if self.dataset.mode == 'image' else f'_{frame}')  # img.txt
                gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]  # normalization gain whwh
                if len(det):
                    # Rescale boxes from img_size to im0 size
                    det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()

                    # Print results
                    for c in det[:, -1].unique():
                        n = (det[:, -1] == c).sum()  # detections per class
                        s += f"{n} {self.names[int(c)]}{'s' * (n > 1)}, "  # add to string

                    # Write results
                    for *xyxy, conf, cls in reversed(det):
                        if self.save_txt:  # Write to file
                            xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist()  # normalized xywh
                            line = (cls, *xywh, conf) if opt.save_conf else (cls, *xywh)  # label format
                            with open(txt_path + '.txt', 'a') as f:
                                f.write(('%g ' * len(line)).rstrip() % line + '\n')

                        if self.save_img or self.view_img:  # Add bbox to image
                            label = f'{self.names[int(cls)]} {conf:.2f}'
                            plot_one_box(xyxy, im0, label=label, color=self.colors[int(cls)], line_thickness=1)
                        xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist() #to get the centroids
                        box_centroids.append([xywh[0], xywh[1]])
                        labels.appends(label)    
                # Print time (inference + NMS)
                print(f'{s}Done. ({(1E3 * (t2 - t1)):.1f}ms) Inference, ({(1E3 * (t3 - t2)):.1f}ms) NMS')

                # Stream results
                if self.view_img:
                    cv2.imshow(str(p), im0)
                    cv2.waitKey(1)  # 1 millisecond

                # Save results (image with detections)
                if self.save_img:
                    if self.dataset.mode == 'image':
                        cv2.imwrite(save_path, im0)
                        print(f" The image with the result is saved in: {save_path}")
                    else:  # 'video' or 'stream'
                        if vid_path != save_path:  # new video
                            vid_path = save_path
                            if isinstance(vid_writer, cv2.VideoWriter):
                                vid_writer.release()  # release previous video writer
                            if vid_cap:  # video
                                fps = vid_cap.get(cv2.CAP_PROP_FPS)
                                w = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                h = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            else:  # stream
                                fps, w, h = 30, im0.shape[1], im0.shape[0]
                                save_path += '.mp4'
                            vid_writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
                        vid_writer.write(im0)

        if self.save_txt or self.save_img:
            s = f"\n{len(list(self.save_dir.glob('labels/*.txt')))} labels saved to {self.save_dir / 'labels'}" if save_txt else ''
            #print(f"Results saved to {save_dir}{s}")

        print(f'Done. ({time.time() - t0:.3f}s)')
        return box_centroids, labels

    
    
    def prediction(self):
        with self._lock:
            with torch.no_grad():
                box_centroids = []
                labels=[]
                if self.opt_update:  # update all models (to fix SourceChangeWarning)
                    for self.weights in ['yolov7.pt']:
                        box_centroids = self.detect()
                        strip_optimizer(self.weights)
                else:
                        box_centroids = self.detect()

            #to publish image and return centroids
            #self.img_pub.publish(ros_numpy.msgify(Image, im2, encoding="rgb8"))
            return box_centroids
        
        
    def imageto3D(self, msg):
        image2D = np.array([])
        fetchcam_intrinsic = np.array([[527.1341414037195, 0.0, 323.8974379222906], 
                                        [0.0, 525.9099904918304, 227.2282369544078], 
                                        [0.0, 0.0, 1.0]])

        detectionmsg_actual3d = ObjectDetectionArray()#after all conversions
        box_2D_centroids = self.prediction()

        for i in range(len(box_2D_centroids)):
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

              


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', nargs='+', type=str, default='yolov7.pt', help='model.pt path(s)')
    parser.add_argument('--source', type=str, default='inference/images', help='source')  # file/folder, 0 for webcam
    parser.add_argument('--img-size', type=int, default=640, help='inference size (pixels)')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='IOU threshold for NMS')
    parser.add_argument('--device', default='', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--view-img', action='store_true', help='display results')
    parser.add_argument('--save-txt', action='store_true', help='save results to *.txt')
    parser.add_argument('--save-conf', action='store_true', help='save confidences in --save-txt labels')
    parser.add_argument('--nosave', action='store_true', help='do not save images/videos')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --class 0, or --class 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--update', action='store_true', help='update all models')
    parser.add_argument('--project', default='runs/detect', help='save results to project/name')
    parser.add_argument('--name', default='exp', help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', help='existing project/name ok, do not increment')
    parser.add_argument('--no-trace', action='store_true', help='don`t trace model')
    opt = parser.parse_args()

    rospy.init_node("Yolo_Predictor")
    foo = NeuralNet()
    while not rospy.is_shutdown():
        rospy.spin()




