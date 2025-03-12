# app.py - Modified Flask application for the boiler simulation with added instability

from flask import Flask, render_template, jsonify, request
import time
import threading
import json
import math
import random  # Added for random disturbances

app = Flask(__name__)

# Simulation parameters
ROOM_TEMP = 20.0  # Keep as is
MAX_TEMP = 100.0  # Keep as is
HEATER_POWER = 3.0  # Reduce from 5.0 for gentler heating
COOLING_RATE = 0.05  # Reduce from 0.1 for slower cooling
SIMULATION_INTERVAL = 0.1  # Keep as is
MAX_HISTORY = 300  # number of data points to keep
TIME_SPEEDUP = 1.0  # default time speed multiplier (can be changed via API)

# Instability parameters
CONTROL_DELAY = 1.0  # Reduce from 2.0 for faster response
OSCILLATION_PERIOD = 10.0  # Increase from original value for smoother oscillation
OSCILLATION_AMPLITUDE = 0.3  # Reduce for less natural variation
RANDOM_DISTURBANCE_MAX = 0.5  # Reduce for more predictable behavior
THERMAL_INERTIA = 4.0  # Increase for more damping (more resistance to change)
HEATER_VARIABILITY = 0.1  # Reduce from 0.3 for more consistent heating

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
        
        # Delay queue for control actions
        self.delayed_actions = []  # (time, action) tuples
        
        # System state variables for instability
        self.thermal_inertia = THERMAL_INERTIA  # resistance to temperature change
        self.oscillation_phase = 0.0  # phase of oscillation
        self.last_disturbance_time = 0.0  # time of last random disturbance
        self.convection_currents = 0.0  # simulated air convection effects
        
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
    
    # Process delayed control actions
    current_sim_time = state.time
    pending_actions = []
    for action_time, action_value in state.delayed_actions:
        if action_time <= current_sim_time:
            # Apply delayed action
            state.heater_on = action_value
        else:
            # Keep this action for later
            pending_actions.append((action_time, action_value))
    state.delayed_actions = pending_actions
    
    # Calculate temperature change
    if state.heater_on:
        # Heating (with non-linear effects and variability)
        heater_efficiency = 1.0 - (HEATER_VARIABILITY * (0.5 - random.random()))
        heat_rate = HEATER_POWER * heater_efficiency * (1 - (state.temperature / MAX_TEMP) ** 2)
        
        # Add non-linearity that increases as temperature rises
        heat_rate *= (1.0 - 0.3 * math.sin(state.temperature / 10.0))
        
        temp_change = heat_rate * dt
    else:
        temp_change = 0
    
    # Cooling (always happens, proportional to difference from room temp)
    # Added non-linearity to cooling based on current temperature
    cooling_factor = COOLING_RATE * (1 + 0.2 * math.sin(state.temperature / 15.0))
    cooling = cooling_factor * (state.temperature - ROOM_TEMP) * dt
    
    # Apply thermal inertia (resistance to temperature change)
    temp_change = temp_change / state.thermal_inertia
    cooling = cooling / state.thermal_inertia
    
    # Add oscillatory behavior (simulating convection currents)
    state.oscillation_phase += dt * 60 * (2 * math.pi / OSCILLATION_PERIOD)  
    oscillation = OSCILLATION_AMPLITUDE * math.sin(state.oscillation_phase)
    
    # Add random disturbances occasionally (every ~10-15 seconds of simulation time)
    random_disturbance = 0
    if (state.time - state.last_disturbance_time) > (10 + 5 * random.random()):
        random_disturbance = (random.random() * 2 - 1) * RANDOM_DISTURBANCE_MAX
        state.last_disturbance_time = state.time
        print(f"Random disturbance: {random_disturbance:.2f}°C at time {state.time:.1f}s")
    
    # Update convection currents based on temperature difference and random factors
    state.convection_currents = 0.8 * state.convection_currents + 0.2 * (
        0.5 * math.sin(state.time / 3.0) - 0.3 * math.cos(state.time / 7.0)
    )
    convection_effect = state.convection_currents * 0.8
    
    # Update temperature with all effects
    state.temperature = state.temperature + temp_change - cooling + oscillation + random_disturbance + convection_effect
    
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

# Modified heater control to include delay
def set_heater_with_delay(on):
    # Calculate when this action should take effect
    effect_time = state.time + CONTROL_DELAY
    
    # Add to the delayed actions queue
    state.delayed_actions.append((effect_time, on))
    
    # For user feedback, we'll say the heater is in the state they requested
    # even though it hasn't actually changed yet
    return on

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

# Add route to adjust instability parameters
@app.route('/api/instability', methods=['POST'])
def set_instability():
    data = request.json
    
    if 'thermal_inertia' in data:
        state.thermal_inertia = max(0.5, float(data['thermal_inertia']))
    
    if 'oscillation_amplitude' in data and 'oscillation_period' in data:
        global OSCILLATION_AMPLITUDE, OSCILLATION_PERIOD
        OSCILLATION_AMPLITUDE = max(0, float(data['oscillation_amplitude']))
        OSCILLATION_PERIOD = max(0.1, float(data['oscillation_period']))
    
    if 'random_max' in data:
        global RANDOM_DISTURBANCE_MAX
        RANDOM_DISTURBANCE_MAX = max(0, float(data['random_max']))
    
    if 'control_delay' in data:
        global CONTROL_DELAY
        CONTROL_DELAY = max(0, float(data['control_delay']))
    
    return jsonify({
        'success': True,
        'thermal_inertia': state.thermal_inertia,
        'oscillation_amplitude': OSCILLATION_AMPLITUDE,
        'oscillation_period': OSCILLATION_PERIOD,
        'random_max': RANDOM_DISTURBANCE_MAX,
        'control_delay': CONTROL_DELAY
    })

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
        'time_speedup': state.time_speedup,
        'instability': {
            'thermal_inertia': state.thermal_inertia,
            'oscillation_amplitude': OSCILLATION_AMPLITUDE,
            'oscillation_period': OSCILLATION_PERIOD,
            'random_max': RANDOM_DISTURBANCE_MAX,
            'control_delay': CONTROL_DELAY
        }
    })

@app.route('/api/heater', methods=['POST'])
def control_heater():
    data = request.json
    if 'on' in data:
        # Apply control with delay
        heater_on = set_heater_with_delay(data['on'])
        print(f"Heater will be set to {'ON' if heater_on else 'OFF'} after delay")
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