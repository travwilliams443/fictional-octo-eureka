# app.py - Flask application for the boiler simulation

from flask import Flask, render_template, jsonify, request
import time
import threading
import json
import math

app = Flask(__name__)

# Simulation parameters
ROOM_TEMP = 20.0  # degrees Celsius
MAX_TEMP = 100.0  # degrees Celsius
HEATER_POWER = 5.0  # degrees per minute (base rate)
COOLING_RATE = 0.1  # proportion of difference with room temp per minute (base rate)
SIMULATION_INTERVAL = 0.1  # seconds between simulation steps
MAX_HISTORY = 300  # number of data points to keep
TIME_SPEEDUP = 1.0  # default time speed multiplier (can be changed via API)

# Global state
class BoilerState:
    def __init__(self):
        self.temperature = ROOM_TEMP
        self.heater_on = False
        self.heater_control_auto = False
        self.target_temp = 60.0
        self.history = []
        self.time = 0
        self.last_update = time.time()
        self.time_speedup = TIME_SPEEDUP  # simulation speed multiplier
        
        # PID parameters - these can be adjusted via API
        self.kp = 1.0  # proportional gain
        self.ki = 0.1  # integral gain
        self.kd = 0.1  # derivative gain
        
        # PID internal state
        self.error_sum = 0
        self.last_error = 0
        
state = BoilerState()

# Simulation thread
def simulation_loop():
    while True:
        update_simulation()
        time.sleep(SIMULATION_INTERVAL)

def update_simulation():
    current_time = time.time()
    dt = (current_time - state.last_update) / 60.0  # convert to minutes
    dt = dt * state.time_speedup  # Apply time speedup multiplier
    state.last_update = current_time
    
    # Calculate temperature change
    if state.heater_on:
        # Heating (with non-linear effects to simulate real physics)
        heat_rate = HEATER_POWER * (1 - (state.temperature / MAX_TEMP) ** 2)
        temp_change = heat_rate * dt
    else:
        temp_change = 0
    
    # Cooling (always happens, proportional to difference from room temp)
    cooling = COOLING_RATE * (state.temperature - ROOM_TEMP) * dt
    
    # Update temperature
    state.temperature = state.temperature + temp_change - cooling
    
    # Add to history
    state.time += SIMULATION_INTERVAL
    state.history.append({
        'time': state.time,
        'temperature': state.temperature,
        'heater_on': state.heater_on,
        'target': state.target_temp
    })
    
    # Trim history if too long
    if len(state.history) > MAX_HISTORY:
        state.history = state.history[-MAX_HISTORY:]

# Add routes for simulation controls
@app.route('/api/disturbance', methods=['POST'])
def add_disturbance():
    data = request.json
    if data.get('type') == 'door_open':
        # Simulate door opening by rapidly dropping temperature
        state.temperature -= 10.0  # Sudden drop by 10 degrees
        return jsonify({'success': True, 'message': 'Door opened - temperature dropped'})
    return jsonify({'success': False, 'message': 'Unknown disturbance type'})

@app.route('/api/simulation_speed', methods=['POST'])
def set_simulation_speed():
    data = request.json
    if 'speedup' in data:
        speedup = float(data['speedup'])
        # Limit to reasonable values
        speedup = max(1.0, min(50.0, speedup))
        state.time_speedup = speedup
        return jsonify({'success': True, 'time_speedup': state.time_speedup})
    return jsonify({'success': False, 'message': 'Missing speedup parameter'})

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/state')
def get_state():
    return jsonify({
        'current_temp': state.temperature,
        'heater_on': state.heater_on,
        'auto_control': state.heater_control_auto,
        'target_temp': state.target_temp,
        'history': state.history,
        'pid': {
            'kp': state.kp,
            'ki': state.ki,
            'kd': state.kd
        },
        'time_speedup': state.time_speedup
    })

@app.route('/api/heater', methods=['POST'])
def control_heater():
    data = request.json
    if 'on' in data:
        # Always respect heater control requests, from either manual or auto modes
        state.heater_on = data['on']
        print(f"Heater set to {'ON' if state.heater_on else 'OFF'}")
    return jsonify({'success': True, 'heater_on': state.heater_on})

@app.route('/api/auto_control', methods=['POST'])
def set_auto_control():
    data = request.json
    if 'enabled' in data:
        state.heater_control_auto = data['enabled']
        # Reset PID state when enabling auto control
        if state.heater_control_auto:
            state.error_sum = 0
            state.last_error = 0
    return jsonify({'success': True, 'auto_control': state.heater_control_auto})

@app.route('/api/target', methods=['POST'])
def set_target():
    data = request.json
    if 'temperature' in data:
        state.target_temp = float(data['temperature'])
    return jsonify({'success': True, 'target_temp': state.target_temp})

@app.route('/api/pid', methods=['POST'])
def set_pid():
    data = request.json
    if 'kp' in data:
        state.kp = float(data['kp'])
    if 'ki' in data:
        state.ki = float(data['ki'])
    if 'kd' in data:
        state.kd = float(data['kd'])
    return jsonify({'success': True, 'pid': {'kp': state.kp, 'ki': state.ki, 'kd': state.kd}})

if __name__ == '__main__':
    # Start simulation thread
    sim_thread = threading.Thread(target=simulation_loop, daemon=True)
    sim_thread.start()
    
    app.run(host='0.0.0.0', debug=True, threaded=True)