FROM osrf/ros:melodic-desktop-full

COPY . /fetch_sfm_ws/src
WORKDIR /fetch_sfm_ws

RUN bash -c " apt update &&\
    apt install python3-catkin-tools python-pip vim iproute2 -y &&\
    rosdep install --from-paths src --ignore-src -r -y &&\
    source /opt/ros/melodic/setup.sh &&\
    catkin config --extend /opt/ros/melodic --cmake-args -DCMAKE_BUILD_TYPE=Release -Wno-dev&&\
    catkin_make"

RUN pip install scipy sklearn