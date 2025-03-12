# pid_controller.py - Enhanced PID controller with improved anti-windup protection

import requests
import time
import sys
import json
import argparse
import signal
from collections import deque

# Default configuration
DEFAULT_URL = 'http://127.0.0.1:5000'  # Flask app URL
DEFAULT_UPDATE_INTERVAL = 0.5  # seconds

class PIDController:
    def __init__(self, base_url, update_interval=DEFAULT_UPDATE_INTERVAL, 
                filter_samples=5, deadband=0.5, min_heater_duration=0.5):
        self.base_url = base_url
        self.update_interval = update_interval
        self.running = False
        
        # Enhanced PID configuration
        self.filter_samples = filter_samples
        self.deadband = deadband
        self.min_heater_duration = min_heater_duration
        
        # Anti-windup configurations
        self.max_integral = 15.0  # Maximum absolute value for integral term
        self.reset_integral_threshold = 8.0  # Reset integral if error crosses zero by this amount
        self.conditional_integration = True  # Only integrate when P term isn't saturated
        
        # Initialize PID state
        self.error_sum = 0
        self.last_error = 0
        self.last_time = time.time()
        self.recent_temps = deque(maxlen=filter_samples)
        self.recent_outputs = deque(maxlen=3)
        self.heater_state_duration = 0
        self.last_heater_state = False
        self.prev_error_sign = 0  # Track error sign for sign change detection
        
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
    
    def filter_temperature(self, current_temp):
        """
        Apply a moving average filter to reduce noise in temperature readings
        """
        self.recent_temps.append(current_temp)
        return sum(self.recent_temps) / len(self.recent_temps)
    
    def filter_output(self, output):
        """
        Apply a filter to smooth control output and prevent rapid oscillations
        """
        self.recent_outputs.append(output)
        # Weighted average with more weight on recent outputs
        if len(self.recent_outputs) == 3:
            return 0.5 * self.recent_outputs[-1] + 0.3 * self.recent_outputs[-2] + 0.2 * self.recent_outputs[-3]
        elif len(self.recent_outputs) == 2:
            return 0.7 * self.recent_outputs[-1] + 0.3 * self.recent_outputs[-2]
        else:
            return output
    
    def apply_deadband(self, error):
        """
        Apply deadband to error to prevent control action on small errors
        """
        if abs(error) < self.deadband:
            return 0
        else:
            # Preserve sign but reduce magnitude by deadband
            return error - (self.deadband * (1 if error > 0 else -1))
    
    def manage_integral_term(self, error, p_term, dt):
        """
        Enhanced integral management with multiple anti-windup strategies
        """
        # Strategy 1: Check for error sign change (indicating setpoint crossing)
        current_sign = 1 if error > 0 else (-1 if error < 0 else 0)
        if self.prev_error_sign != 0 and current_sign != 0 and self.prev_error_sign != current_sign:
            # If error has changed sign and is significant, reset integral
            if abs(error) > self.reset_integral_threshold:
                print(f"🔄 Error changed sign significantly ({self.prev_error_sign} to {current_sign}). Resetting integral term.")
                self.error_sum = 0
        self.prev_error_sign = current_sign
        
        # Strategy 2: Conditional integration (only integrate when P term isn't saturated)
        # This prevents integral wind-up when the controller can't affect the process
        if not self.conditional_integration or abs(p_term) < 20:
            # Only accumulate integral within reasonable range
            self.error_sum += error * dt
            
        # Strategy 3: Clamp the integral term to prevent excessive wind-up
        self.error_sum = max(-self.max_integral, min(self.error_sum, self.max_integral))
        
        return self.error_sum
    
    def pid_calculation(self, state):
        """
        Calculates PID output with enhanced anti-windup protection
        """
        # Extract values from state
        current_temp = state['current_temp']
        target_temp = state['target_temp']
        kp = state['pid']['kp']
        ki = state['pid']['ki']
        kd = state['pid']['kd']
        
        # Filter temperature to reduce noise
        filtered_temp = self.filter_temperature(current_temp)
        
        # Calculate time delta
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time
        
        # Calculate error
        error = target_temp - filtered_temp
        
        # Apply deadband to error
        deadband_error = self.apply_deadband(error)
        
        # Calculate PID components
        p_term = kp * deadband_error
        
        # Enhanced integral management
        self.error_sum = self.manage_integral_term(error, p_term, dt)
        i_term = ki * self.error_sum
        
        # Derivative term (on measurement, not error, to avoid derivative kick)
        d_term = -kd * (filtered_temp - self.last_error) / dt if dt > 0 else 0
        self.last_error = filtered_temp
        
        # Calculate total output
        output = p_term + i_term + d_term
        
        # Apply output filtering to smooth control response
        filtered_output = self.filter_output(output)
        
        # Debug output
        print(f"Current: {current_temp:.2f}°C (Filtered: {filtered_temp:.2f}°C), Target: {target_temp:.2f}°C")
        print(f"Error: {error:.2f}°C, Deadband Error: {deadband_error:.2f}°C")
        print(f"P: {p_term:.2f}, I: {i_term:.2f} (sum={self.error_sum:.2f}), D: {d_term:.2f}")
        print(f"Raw Output: {output:.2f}, Filtered Output: {filtered_output:.2f}")
        
        # Convert to binary output for heating control
        heater_on = filtered_output > 0
        
        # Track heater state duration
        if heater_on != self.last_heater_state:
            if self.heater_state_duration < self.min_heater_duration:
                # Keep current state if we haven't met minimum duration
                heater_on = self.last_heater_state
                print(f"Minimum state duration not met. Maintaining current state.")
            else:
                # Reset duration counter for state change
                self.heater_state_duration = 0
                self.last_heater_state = heater_on
        else:
            # Increment duration for same state
            self.heater_state_duration += dt
        
        # Debug the actual decision
        print(f"Decision: Heater {'ON' if heater_on else 'OFF'} (State Duration: {self.heater_state_duration:.1f}s)")
        print("-" * 40)
        
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
        print("Starting Enhanced PID controller with improved anti-windup protection...")
        print("Anti-windup strategies active:")
        print("1. Error sign change detection & reset")
        print("2. Conditional integration")
        print("3. Integral term clamping")
        print("4. Filtered temperature and output")
        print("-" * 60)
        
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
    parser = argparse.ArgumentParser(description="Enhanced PID Controller with Anti-Windup Protection")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL of the Flask app")
    parser.add_argument("--interval", type=float, default=DEFAULT_UPDATE_INTERVAL, 
                        help="Update interval in seconds")
    parser.add_argument("--filter", type=int, default=5, 
                        help="Number of samples for temperature filtering")
    parser.add_argument("--deadband", type=float, default=0.5, 
                        help="Deadband in degrees Celsius")
    parser.add_argument("--min-duration", type=float, default=0.5, 
                        help="Minimum heater state duration in seconds")
    parser.add_argument("--max-integral", type=float, default=15.0,
                        help="Maximum integral term value (anti-windup)")
    
    args = parser.parse_args()
    
    # Register signal handler for clean exit
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run controller
    controller = PIDController(
        args.url, 
        args.interval, 
        filter_samples=args.filter,
        deadband=args.deadband,
        min_heater_duration=args.min_duration
    )
    controller.max_integral = args.max_integral
    controller.run()