import socket
import struct
import serial
import time

# Configuration
UDP_IP = "0.0.0.0"
UDP_PORT = 5300
SERIAL_PORT = "COM9"
BAUD_RATE = 9600

def parse_fh5_telemetry(data):
    """
    Parse Forza Horizon 5 telemetry data using correct Sled format offsets
    FH5 uses Sled format which is different from FM7 Dash format
    """
    try:
        if len(data) < 324:
            return None, None, None
        
        # Sled format correct offsets:
        # IsRaceOn = 0 (s32)
        # TimestampMS = 4 (u32)
        # EngineMaxRpm = 8 (f32)
        # EngineIdleRpm = 12 (f32)
        # CurrentEngineRpm = 16 (f32)
        
        # AccelerationX/Y/Z = 20, 24, 28 (f32)
        # VelocityX/Y/Z = 32, 36, 40 (f32)
        # AngularVelocityX/Y/Z = 44, 48, 52 (f32)
        # Yaw/Pitch/Roll = 56, 60, 64 (f32)
        
        # Gear = 319 (u8) - This is the correct offset for Sled format
        # Speed = 256 (f32) - Speed in m/s
        
        # Alternative: Calculate speed from velocity vectors
        vel_x = struct.unpack('f', data[32:36])[0]
        vel_y = struct.unpack('f', data[36:40])[0]
        vel_z = struct.unpack('f', data[40:44])[0]
        
        # Calculate actual speed from velocity vector
        speed_ms = (vel_x**2 + vel_y**2 + vel_z**2)**0.5
        speed_kmh = abs(speed_ms * 3.6)
        
        # Current engine RPM
        rpm = struct.unpack('f', data[16:20])[0]
        
        # Gear - try byte 319 for Sled format
        gear = struct.unpack('B', data[319:320])[0]
        
        # Gear adjustment (Sled format uses 0=reverse, 1=neutral, 2=1st, etc)
        if gear == 0:
            gear = -1  # Reverse
        elif gear == 1:
            gear = 0  # Neutral
        else:
            gear = gear   # Shift down by 1 (2 becomes 1, 3 becomes 2, etc)
        
        return int(speed_kmh), int(rpm), gear
        
    except Exception as e:
        print(f"Error parsing telemetry: {e}")
        return None, None, None

def main():
    print("Forza Horizon 5 to Arduino Telemetry Bridge v2")
    print("=" * 50)
    
    # Setup UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(1.0)
    print(f"✓ UDP socket listening on port {UDP_PORT}")
    
    # Setup Serial connection to Arduino
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print(f"✓ Connected to Arduino on {SERIAL_PORT} at {BAUD_RATE} baud")
    except serial.SerialException as e:
        print(f"✗ Failed to connect to Arduino: {e}")
        return
    
    print("\nWaiting for Forza Horizon 5 telemetry data...")
    print("Press Ctrl+C to exit\n")
    
    packet_count = 0
    last_print_time = time.time()
    
    try:
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                packet_count += 1
                
                # Parse telemetry
                speed, rpm, gear = parse_fh5_telemetry(data)
                
                if speed is not None:
                    # Send to Arduino
                    message = f"{speed},{rpm},{gear}\n"
                    ser.write(message.encode())
                    
                    # Print status every second
                    current_time = time.time()
                    if current_time - last_print_time >= 1.0:
                        gear_str = "N" if gear == 0 else ("R" if gear < 0 else str(gear))
                        print(f"[{packet_count:6d}] Speed: {speed:3d} km/h | RPM: {rpm:5d} | Gear: {gear_str}")
                        last_print_time = current_time
                        
            except socket.timeout:
                continue
                
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        sock.close()
        ser.close()
        print("✓ Connections closed")
        print(f"Total packets processed: {packet_count}")

if __name__ == "__main__":
    main()