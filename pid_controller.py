# pid_controller.py - PID controller for the boiler simulation

import requests
import time
import sys
import json
import argparse
import signal

# Default configuration
DEFAULT_URL = 'http://localhost:5000'  # Flask app URL
DEFAULT_UPDATE_INTERVAL = 0.5  # seconds

class PIDController:
    def __init__(self, base_url, update_interval=DEFAULT_UPDATE_INTERVAL):
        self.base_url = base_url
        self.update_interval = update_interval
        self.running = False
        
        # Initialize PID state
        self.error_sum = 0
        self.last_error = 0
        self.last_time = time.time()
        
    def get_state(self):
        try:
            response = requests.get(f"{self.base_url}/api/state")
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching state: {e}")
            return None
    
    def set_heater(self, on):
        try:
            response = requests.post(
                f"{self.base_url}/api/heater",
                json={"on": on}
            )
            return response.json()
        except requests.RequestException as e:
            print(f"Error setting heater: {e}")
            return None
    
    def pid_calculation(self, state):
        """
        Calculates PID output based on current state
        """
        # Extract values from state
        current_temp = state['current_temp']
        target_temp = state['target_temp']
        kp = state['pid']['kp']
        ki = state['pid']['ki']
        kd = state['pid']['kd']
        
        # Calculate time delta
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time
        
        # Calculate error
        error = target_temp - current_temp
        
        # Calculate PID components
        p_term = kp * error
        
        # Integral term (with anti-windup)
        self.error_sum += error * dt
        # Anti-windup - limit the integral term
        max_integral = 20 / ki if ki > 0 else 0
        self.error_sum = max(-max_integral, min(self.error_sum, max_integral))
        i_term = ki * self.error_sum
        
        # Derivative term (on measurement, not error, to avoid derivative kick)
        d_term = -kd * (current_temp - self.last_error) / dt if dt > 0 else 0
        self.last_error = current_temp
        
        # Calculate total output
        output = p_term + i_term + d_term
        
        # Debug output
        print(f"Current: {current_temp:.2f}°C, Target: {target_temp:.2f}°C, Error: {error:.2f}°C")
        print(f"P: {p_term:.2f}, I: {i_term:.2f}, D: {d_term:.2f}, Output: {output:.2f}")
        
        # Convert to binary output for heating control
        # Positive output means we need to heat (current < target)
        # Negative output means we need to cool (current > target)
        heater_on = output > 0
        
        # Debug the actual decision
        print(f"Decision: Heater {'ON' if heater_on else 'OFF'}")
        
        return heater_on
    
    def enable_auto_control(self):
        """
        Enables automatic control mode in the simulation
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/auto_control",
                json={"enabled": True}
            )
            return response.json()
        except requests.RequestException as e:
            print(f"Error enabling auto control: {e}")
            return None
    
    def run(self):
        """
        Main control loop
        """
        print("Starting PID controller...")
        self.running = True
        self.enable_auto_control()
        
        try:
            while self.running:
                # Get current state
                state = self.get_state()
                if not state:
                    time.sleep(self.update_interval)
                    continue
                
                # Skip if auto control is disabled
                if not state['auto_control']:
                    print("Auto control disabled. Waiting...")
                    time.sleep(self.update_interval)
                    continue
                
                # Calculate PID output
                heater_on = self.pid_calculation(state)
                
                # Send control signal
                self.set_heater(heater_on)
                
                # Wait for next update
                time.sleep(self.update_interval)
        
        except KeyboardInterrupt:
            print("\nStopping PID controller...")
        finally:
            self.running = False
    
    def stop(self):
        """
        Stop the control loop
        """
        self.running = False


def signal_handler(sig, frame):
    print("\nStopping PID controller...")
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PID Controller for Boiler Simulation")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL of the Flask app")
    parser.add_argument("--interval", type=float, default=DEFAULT_UPDATE_INTERVAL, 
                        help="Update interval in seconds")
    args = parser.parse_args()
    
    # Register signal handler for clean exit
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run controller
    controller = PIDController(args.url, args.interval)
    controller.run()