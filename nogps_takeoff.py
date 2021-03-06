import RPi.GPIO as GPIO                                                         # Needed to read ultrasonic sensors
import time, sys, datetime, pytz, tzlocal, os, pickle, multiprocessing          # Needed for many basic functions and to satisfy preconditions
from datetime import datetime                                                   # Needed to generate timestamp
from dateutil import tz                                                         # Needed to generate timestamp
from dronekit import *                                                          # Needed for all drone-related commands
from pymavlink import mavutil

def arm_and_takeoff_nogps(aTargetAltitude):

    """This function arms vehicle and flies to aTargetAltitude without GPS data in ALT_HOLD Mode. """

    # The following command disables all arming checks. Be careful, this is very dangerous: vehicle.parameters['ARMING_CHECK']=0

    global stdata_q

    ##### CONSTANTS #####
    DEFAULT_TAKEOFF_THRUST = 0.3
    SMOOTH_TAKEOFF_THRUST = 0.1

    # Don't let the user try to arm until autopilot is ready
    # If you need to disable the arming check, just comment it with your own responsibility:

    # print("Basic pre-arm checks")
    # while not vehicle.is_armable:
    #     print(" Waiting for vehicle to initialise...")
    #     time.sleep(1)

    while vehicle.parameters['ARMING_CHECK'] != -9:                             # Confirm that GPS check has been disabled
        vehicle.parameters['ARMING_CHECK'] = -9
        time.sleep(0.2)

    while vehicle.mode != VehicleMode("ALT_HOLD"):
        print("Waiting for ALT_HOLD...")
        vehicle.mode = VehicleMode("ALT_HOLD")                                  # Copter should arm in ALT_HOLD mode
        print "Mode: " + vehicle.mode.name
        time.sleep(0.2)
    print "Mode: " + vehicle.mode.name

    time.sleep(1)
    print("Flushing queue...")
    vehicle.flush()                                                             # Forces DroneKit to send all outstanding messages

    print("Arming motors...")
    while not vehicle.armed:                                                    # This loops ensures that the vehicle is armed before attempting takeoff
        print(" Waiting for arming...")
        vehicle.armed = True                                                    # Arms Vehicle
        time.sleep(1)

    print("Vehicle Armed!")

    print("Confirming Mode...")
    while vehicle.mode != "ALT_HOLD":
        vehicle.mode = VehicleMode("ALT_HOLD")                                  # Copter should arm in ALT_HOLD mode
        print "Mode: " + vehicle.mode.name

    print("Taking off!")

    thrust = DEFAULT_TAKEOFF_THRUST

    while True:
        print("Retrieving altitude data for takeoff...")
        sensor_data = stdata_q.get()
        current_altitude = sensor_data[5]/100
        print " Altitude: " + str(current_altitude)

        if current_altitude >= 0.9:                                             # Trigger just below target alt.
            print("Reached target altitude")
            break

        elif current_altitude >= 0.6 and current_altitude < 0.8:                #Slighlty decrease thrust at 0.6 x Target Altitude
            thrust = SMOOTH_TAKEOFF_THRUST
            print("Smoothing thrust...")

        set_attitude(thrust = thrust)
        print("Flushing queue...")
        vehicle.flush()                                                         # Forces DroneKit to send all outstanding MAVlink messages
        time.sleep(0.2)

def timestamp():

    #### This function generates a timestemp which will be written to the log file ####

    local_timezone = tzlocal.get_localzone()
    utc_time = datetime.utcnow()

    # Convert time zone
    local_time= utc_time.replace(tzinfo=pytz.utc).astimezone(local_timezone)
    timestamp_local = local_time.strftime('%m-%d-%Y %H:%M:%S %Z')
    return timestamp_local

def land_and_close():
    print "Switching to STABILIZE mode to begin landing..."
    vehicle.mode    = VehicleMode("STABILIZE")

    print "Stabilizing & Ceasing all movement..."

    time.sleep(2)

    print "Landing..."

    while vehicle.mode != VehicleMode("LAND"):
        print("Waiting for Mode Change to LAND...")
        vehicle.mode = VehicleMode("LAND") # Copter should arm in STABILIZE mode
        print "Mode: " + vehicle.mode.name
        time.sleep(0.2)
    print "Mode: " + vehicle.mode.name

    print "Closing vehicle object..."
    vehicle.close()
    time.sleep(1)
    print "Vehicle Disarmed."

def condition_yaw(heading, direction):

    """
    This function sends a command_long MAVlink command to change the yaw
    or heading of the vehicle. Vehicles running ArduCopter will accept
    parameters for the final yaw, the speed of rotation, the direction
    of rotation, and whether the final yaw is relative or absolute with
    the MAVlink command MAV_CMD_CONDITION_YAW.
    """

    msg = vehicle.message_factory.command_long_encode(
        0, 0,                                           # target system, target component
        mavutil.mavlink.MAV_CMD_CONDITION_YAW,          # command
        0,                                              # confirmation
        heading,                                        # param 1, yaw in degrees
        0,                                              # param 2, yaw speed deg/s
        direction,                                      # param 3, direction -1 ccw, 1 cw
        1,                                              # param 4, relative offset 1, absolute angle 0
        0, 0, 0)                                        # param 5 ~ 7 not used

    vehicle.send_mavlink(msg)                           # send command to vehicle

    if duration != 0:
        modf = math.modf(duration)                      # Divide the duration into the frational and integer parts

        time.sleep(modf[0])                             # Sleep for the fractional parts of duration

        for x in range(0,int(modf[1])):                 # Send command to vehicle on 1 Hz cycle
            time.sleep(1)
            vehicle.send_mavlink(msg)

def change_alt(altitude = 1, speed = 0.2, duration = 0):

    """
    This function sends a command_long MAVlink command to change the altitude
    of the vehicle. Vehicles running ArduCopter will accept parameters for
    vertical speed and final altitude with the MAVlink command MAV_CMD_CONDITION_CHANGE_ALT.
    """

    # Note that from AC3.3 the message should be re-sent every second (after about 3 seconds with no message the velocity will drop back to zero).
    # In AC3.2.1 and earlier the specified velocity persists until it is canceled.
    # The code below should work on either version (sending the message multiple times does not cause problems).

    msg = vehicle.message_factory.command_long_encode(
        0, 0,                                           # target system, target component
        mavutil.mavlink.MAV_CMD_CONDITION_CHANGE_ALT,   # command
        0,                                              # confirmation
        speed,                                          # param 1, speed in m/s or cm/s (?)
        0, 0, 0, 0, 0,                                  # param 2 - 6 not used
        altitude)                                       # param 7, final altitude

    vehicle.send_mavlink(msg)                           # send command to vehicle

    if duration != 0:
        modf = math.modf(duration)                      # Divide the duration into the frational and integer parts

        time.sleep(modf[0])                             # Sleep for the fractional parts of duration

        for x in range(0,int(modf[1])):                 # Send command to vehicle on 1 Hz cycle
            time.sleep(1)
            vehicle.send_mavlink(msg)

def change_speed(speed = 0.5, duration = 0):

    """
    This function sends a command_long MAVlink command to change the
    horizonatal speed of the vehicle. Vehicles running ArduCopter will
    accept a parameter horizonatal speed with the MAVlink command MAV_CMD_DO_CHANGE_SPEED.
    """

    # Note that from AC3.3 the message should be re-sent every second (after about 3 seconds with no message the velocity will drop back to zero).
    # In AC3.2.1 and earlier the specified velocity persists until it is canceled.
    # The code below should work on either version (sending the message multiple times does not cause problems).

    msg = vehicle.message_factory.command_long_encode(
        0, 0,                                           # target system, target component
        mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,   # command
        0,                                              # confirmation
        0,                                              # param 1, not used
        speed,                                          # param 2, speed in m/s
        0, 0, 0, 0, 0)                                  # param 3 - 7 not used

    vehicle.send_mavlink(msg)

    if duration != 0:
        # Divide the duration into the frational and integer parts
        modf = math.modf(duration)

        # Sleep for the fractional part
        time.sleep(modf[0])

        # Send command to vehicle on 1 Hz cycle
        for x in range(0,int(modf[1])):
            time.sleep(1)
            vehicle.send_mavlink(msg)

def set_attitude(roll_angle = 0.0, pitch_angle = 0.0, yaw_rate = 0.0, thrust = 0.5, duration = 0):

    # Note that from AC3.3 the message should be re-sent every second (after about 3 seconds with no message the velocity will drop back to zero).
    # In AC3.2.1 and earlier the specified velocity persists until it is canceled.
    # The code below should work on either version (sending the message multiple times does not cause problems).

    """
    The roll and pitch rate cannot be controllbed with rate in radian in AC3.4.4 or earlier,
    so you must use quaternion to control the pitch and roll for those vehicles.
    """

    # Thrust >  0.5: Ascend
    # Thrust == 0.5: Hold the altitude
    # Thrust <  0.5: Descend
    # set_roll_pitch_yaw_thrust_encode
    msg = vehicle.message_factory.set_attitude_target_encode(
                                                             0,
                                                             0,
                                                                 # Target system
                                                             0,
                                                                 # Target component
                                                             0b00000000,
                                                                 # Type mask: bit 1 is LSB
                                                             to_quaternion(roll_angle, pitch_angle),
                                                                 # Quaternion
                                                             0,
                                                                 # Body roll rate in radian
                                                             0,
                                                                 # Body pitch rate in radian
                                                             math.radians(yaw_rate),
                                                                 # Body yaw rate in radian
                                                             thrust)
                                                                 # Thrust
    vehicle.send_mavlink(msg)

    if duration != 0:
        # Divide the duration into the frational and integer parts
        modf = math.modf(duration)

        # Sleep for the fractional part
        time.sleep(modf[0])

        # Send command to vehicle on 1 Hz cycle
        for x in range(0,int(modf[1])):
            time.sleep(1)
            vehicle.send_mavlink(msg)

def to_quaternion(roll = 0.0, pitch = 0.0, yaw = 0.0):
    """
    Convert degrees to quaternions
    """
    t0 = math.cos(math.radians(yaw * 0.5))
    t1 = math.sin(math.radians(yaw * 0.5))
    t2 = math.cos(math.radians(roll * 0.5))
    t3 = math.sin(math.radians(roll * 0.5))
    t4 = math.cos(math.radians(pitch * 0.5))
    t5 = math.sin(math.radians(pitch * 0.5))

    w = t0 * t2 * t4 + t1 * t3 * t5
    x = t0 * t3 * t4 - t1 * t2 * t5
    y = t0 * t2 * t5 + t1 * t3 * t4
    z = t1 * t2 * t4 - t0 * t3 * t5

    return [w, x, y, z]

def read_individual_sonar(direction):

    #### This function reads one SR-04 Sensor, returns results in meters, and stores all data in an array. ####
    #### The argument "direction" must be an integer from 0 to 5, inclusive ####

    pulse_start = 0.0                       # This resets variables to default state at the beginning of each iteration
    pulse_end = 0.0                         # --

    if direction == 0:                      # This if-statement sets the Trigger and Echo GPIO pins for each sensor as we iterate
        # Front sonar
        sensortype = "Front"
        TRIG = 33
        ECHO = 37

    elif direction == 1:
        # Right sonar
        sensortype = "Right"
        TRIG = 7
        ECHO = 11

    elif direction == 2:
        # Left sonar
        sensortype = "Left"
        TRIG = 13
        ECHO = 15

    elif direction == 3:
        # Back sonar
        sensortype = "Back"
        TRIG = 16
        ECHO = 18

    elif direction == 4:
        # Top sonar
        sensortype = "Top"
        TRIG = 29
        ECHO = 31

    elif direction == 5:
        # Bottom sonar
        sensortype = "Bottom"
        TRIG = 32
        ECHO = 36
    else:
        raise ValueError("The argument 'direction' must be an integer from 0 to 5, inclusive!")

    GPIO.setup(ECHO,GPIO.IN)                # Sets up GPIO pins
    GPIO.setup(TRIG,GPIO.OUT)               # --

    GPIO.output(TRIG, False)
    time.sleep(0.2)

    GPIO.output(TRIG, True)
    time.sleep(pulse)
    GPIO.output(TRIG, False)

    while GPIO.input(ECHO)==0:
        pulse_start = time.time()

    while GPIO.input(ECHO)==1:
        pulse_end = time.time()
        if pulse_end - pulse_start > 0.5:
            break

    pulse_duration = pulse_end - pulse_start

    if direction == 0:
        # Front sonar
        distance = (pulse_duration*17092) - 15.2979

    elif direction == 1:
        # Right sonar
        distance = (pulse_duration*17092) - 23.7135

    elif direction == 2:
        # Left sonar
        distance = (pulse_duration*17092) - 24.2425

    elif direction == 3:
        # Back sonar
        distance = (pulse_duration*17092) - 15.7859

    elif direction == 4:
        # Top sonar
        distance = (pulse_duration*17092) - 1.098

    elif direction == 5:
        # Bottom sonar
        distance = (pulse_duration*17092) - 6.92

    distance = float(round(distance,2))                         # Rounds the distance to 2 decimal places
    return distance

def logdata(list_to_write, logfile):
    #### This function writes a string to the sensor log file ####

    print "[Sub-process]: Logging data..."
    logfile.write("\n" + "Sonar Data: " + list_to_write)
    print "[Sub-process]: Data logged!"

def read_sonar_multi_call(sensor_loop, stdata_q):

    print "[Sub-process]: Opening sensor log file and timestamping..."
    if os.path.isfile("/home/pi/sensorlog.txt") and os.stat("/home/pi/sensorlog.txt").st_size != 0:         # Here we initialize the sensor log file and write the timestamp
        logfile = open("sensorlog.txt","a")
        logfile.write("\n" + "\n" + timestamp())
    else:
        logfile = open("sensorlog.txt","w")
        logfile.write(timestamp())

    print "[Sub-process]: Initializing pool to read sonar data..."
    while sensor_loop.is_set() == False:

        pool = multiprocessing.Pool(processes=6)
        stdata_pre = [pool.apply_async(read_individual_sonar, args=(x,)) for x in range(6)]
        stdata = [p.get() for p in stdata_pre]
        pool.close()
        logdata(str(stdata), logfile)
        stdata_q.put(stdata)                                                # Sends "stdata" back to main process via multiprocessing queue

    print "[Sub-process]: Closing sensor log file..."
    logfile.close()
    print "[Sub-process]: Rejoining master process..."

if __name__ == "__main__":
    # All code -- including calling pre-defined functions -- goes here
    target = sys.argv[1] if len(sys.argv) >= 2 else 'udpin:0.0.0.0:14550'
    print 'Connecting to ' + target + '...'
    vehicle = connect(target, wait_ready=True)

    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)

    pulse = 0.00002
    stdata = [0,0,0,0,0,0]
    sensor_loop = multiprocessing.Event()

    print "Initializing queue to communicate between processes..."
    stdata_q = multiprocessing.Queue()
    print "Queue initialised!"
    proc = multiprocessing.Process(target=read_sonar_multi_call, args=(sensor_loop, stdata_q,))
    print "Starting sub-process to control sensor reading and writing..."
    proc.start()
    print "Process started!"

    time.sleep(0.5)

    arm_and_takeoff_nogps(1)

    t = 0
    land_and_close()

    print "Triggering sensor_loop event to end sub-process..."
    sensor_loop.set()
    time.sleep(2)
    print "Cleaning up sub-process..."
    proc.join()
    print "Cleaning up GPIO pins..."
    GPIO.cleanup()
    print "Done!"
