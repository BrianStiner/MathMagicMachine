import cv2, os
import numpy as np
import matplotlib.image as mpimg


IN_HEIGHT, IN_WIDTH, IMAGE_CHANNELS = 160, 320, 3
OUT_HEIGHT, OUT_WIDTH = 100, 100
INPUT_SHAPE = (OUT_HEIGHT, OUT_WIDTH, IMAGE_CHANNELS)


def load_image(image_dir):
    """
    Load RGB images from a file
    """
    return np.array(mpimg.imread(image_dir))


def perspective_shift(image):
    """
    Crop the image by 60 from top, 25 from bottom.
    Then, warp perspective to a square
    """
    points1 = np.float32([[60,60],[240,60],[0,135],[320,135]])
    points2 = np.float32([[0,0],[100,0],[0,100],[100,100]])
    M = cv2.getPerspectiveTransform(points1,points2)
    bird_eye = cv2.warpPerspective(image,M,(100,100))
    return bird_eye


def resize(image):
    """
    Resize the image to the input shape used by the network model
    """
    return cv2.resize(image, (OUT_WIDTH, OUT_HEIGHT), cv2.INTER_AREA)


def rgb2yuv(image):
    """
    Convert the image from RGB to YUV (This is what the NVIDIA model does)
    """
    return cv2.cvtColor(image, cv2.COLOR_RGB2YUV)


def preprocess(image):
    """
    Combine all preprocess functions into one
    """
    image = perspective_shift(image)
    image = rgb2yuv(image)
    image = resize(image)
    return image


def choose_image(center, left, right, steering_angle):
    """
    Randomly choose an image from the center, left or right, and adjust
    the steering angle.
    """
    choice = np.random.choice(3)
    if choice == 0:
        return load_image(left), steering_angle + 0.2
    elif choice == 1:
        return load_image(right), steering_angle - 0.2
    return load_image(center), steering_angle


def random_flip(image, steering_angle):
    """
    Randomly flipt the image left <-> right, and adjust the steering angle.
    """
    if np.random.rand() < 0.5:
        image = cv2.flip(image, 1)
        steering_angle = -steering_angle
    return image, steering_angle


def random_translate(image, steering_angle, range_x, range_y):
    """
    Randomly shift the image virtially and horizontally (translation).
    """
    trans_x = range_x * (np.random.rand() - 0.5)
    trans_y = range_y * (np.random.rand() - 0.5)
    steering_angle += trans_x * 0.002
    trans_m = np.float32([[1, 0, trans_x], [0, 1, trans_y]])
    height, width = image.shape[:2]
    image = cv2.warpAffine(image, trans_m, (width, height))
    return image, steering_angle


def random_shadow(image):
    """
    Generates and adds random shadow
    """
    # (x1, y1) and (x2, y2) forms a line
    # xm, ym gives all the locations of the image
    x1, y1 = IN_HEIGHT * np.random.rand(), 0
    x2, y2 = IN_WIDTH * np.random.rand(), IN_HEIGHT
    xm, ym = np.mgrid[0:IN_HEIGHT, 0:IN_WIDTH]

    # mathematically speaking, we want to set 1 below the line and zero otherwise
    # Our coordinate is up side down.  So, the above the line:
    # (ym-y1)/(xm-x1) > (y2-y1)/(x2-x1)
    # as x2 == x1 causes zero-division problem, we'll write it in the below form:
    # (ym-y1)*(x2-x1) - (y2-y1)*(xm-x1) > 0
    mask = np.zeros_like(image[:, :, 1])
    mask[(ym - y1) * (x2 - x1) - (y2 - y1) * (xm - x1) > 0] = 1

    # choose which side should have shadow and adjust saturation
    cond = mask == np.random.randint(2)
    s_ratio = np.random.uniform(low=0.2, high=0.5)

    # adjust Saturation in HLS(Hue, Light, Saturation)
    hls = cv2.cvtColor(image, cv2.COLOR_RGB2HLS)
    hls[:, :, 1][cond] = hls[:, :, 1][cond] * s_ratio
    return cv2.cvtColor(hls, cv2.COLOR_HLS2RGB)


def random_brightness(image):
    """
    Randomly adjust brightness of the image.
    """
    # HSV (Hue, Saturation, Value) is also called HSB ('B' for Brightness).
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    ratio = 1.0 + 0.4 * (np.random.rand() - 0.5)
    hsv[:,:,2] =  hsv[:,:,2] * ratio
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


def augument(center, left, right, steering_angle, range_x=100, range_y=10):
    """
    Generate an augumented image and adjust steering angle.
    (The steering angle is associated with the center image)
    """
    image, steering_angle = choose_image(center, left, right, steering_angle)
    image, steering_angle = random_flip(image, steering_angle)
    image, steering_angle = random_translate(image, steering_angle, range_x, range_y)
    image = random_shadow(image)
    image = random_brightness(image)
    return image, steering_angle


def batch_generator(lines, batch_size, is_training):
    """
    Generate training image give image paths and associated steering angles
    """
    images = np.empty([batch_size, IMAGE_HEIGHT, IMAGE_WIDTH, IMAGE_CHANNELS])
    steers = np.empty(batch_size)
    while True:
        i = 0
        for index in np.random.permutation(len(lines)):
            center, left, right, steering_angle = lines[index][:4]
            steering_angle = float(steering_angle)
            # argumentation
            if is_training and np.random.rand() < 0.7:
                image, steering_angle = augument(center, left, right, steering_angle)
            else:
                image = load_image(center)
            # add the image and steering angle to the batch
            images[i] = preprocess(image)
            steers[i] = steering_angle
            i += 1
            if i == batch_size:
                break
        yield images, steers
