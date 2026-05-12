from roboflow import Roboflow

rf = Roboflow(api_key="8xkhUbOPqPJ53LaR2Vxi")
project = rf.workspace("dwayne-y7phs").project("peso-bill-detection-5kfcf")
version = project.version(4)
dataset = version.download("yolov8")