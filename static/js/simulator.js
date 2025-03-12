// Chart initialization
const ctx = document.getElementById('tempChart').getContext('2d');
const tempChart = new Chart(ctx, {
    type: 'line',
    data: {
        datasets: [
            {
                label: 'Temperature',
                borderColor: function(context) {
                    const index = context.dataIndex;
                    const value = context.dataset.data[index];
                    // Use heater status from point data to determine color
                    return value && value.heaterOn ? 'rgb(255, 99, 132)' : 'rgb(54, 162, 235)';
                },
                backgroundColor: 'rgba(200, 200, 255, 0.1)',
                borderWidth: 2,
                data: [],
                fill: true,
                segment: {
                    borderColor: function(context) {
                        const p0 = context.p0.parsed;
                        return context.p0.raw.heaterOn ? 'rgb(255, 99, 132)' : 'rgb(54, 162, 235)';
                    }
                }
            },
            {
                label: 'Target',
                borderColor: 'rgb(100, 100, 100)',
                borderWidth: 1,
                borderDash: [5, 5],
                pointRadius: 0,
                data: [],
                fill: false
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            x: {
                type: 'linear',
                title: {
                    display: true,
                    text: 'Time (seconds)'
                },
                // Fix for the chart not extending to the left edge
                min: function(context) {
                    const data = context.chart.data.datasets[0].data;
                    if (data.length > 0) {
                        // Show a fixed width window of 30 seconds
                        return Math.floor(data[data.length - 1].x - 30);
                    }
                    return 0;
                },
                max: function(context) {
                    const data = context.chart.data.datasets[0].data;
                    if (data.length > 0) {
                        return Math.ceil(data[data.length - 1].x);
                    }
                    return 30;
                },
                ticks: {
                    // Format the ticks to always be integers
                    callback: function(value) {
                        return Math.round(value);
                    }
                }
            },
            y: {
                title: {
                    display: true,
                    text: 'Temperature (°C)'
                },
                min: 15,
                max: 95
            }
        },
        animation: {
            duration: 0
        }
    }
});

// Tabs functionality
const tabs = document.querySelectorAll('.tab');
const tabContents = document.querySelectorAll('.tab-content');

tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const tabId = tab.getAttribute('data-tab');
        
        // Deactivate all tabs and contents
        tabs.forEach(t => t.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        
        // Activate the clicked tab and its content
        tab.classList.add('active');
        document.getElementById(tabId).classList.add('active');
    });
});

// Heater indicator
const heaterStatus = document.getElementById('heaterStatus');
const currentTempDisplay = document.getElementById('currentTemp');
const targetTempDisplay = document.getElementById('targetTemp');

// Buttons
const heaterToggle = document.getElementById('heaterToggle');
const autoToggle = document.getElementById('autoToggle');
const openDoor = document.getElementById('openDoor');
const resetInstability = document.getElementById('resetInstability');

// Basic sliders
const targetSlider = document.getElementById('targetSlider');
const targetValue = document.getElementById('targetValue');
const speedSlider = document.getElementById('speedSlider');
const speedValue = document.getElementById('speedValue');

// PID sliders
const kpSlider = document.getElementById('kpSlider');
const kpValue = document.getElementById('kpValue');
const kiSlider = document.getElementById('kiSlider');
const kiValue = document.getElementById('kiValue');
const kdSlider = document.getElementById('kdSlider');
const kdValue = document.getElementById('kdValue');

// Instability sliders
const delaySlider = document.getElementById('delaySlider');
const delayValue = document.getElementById('delayValue');
const inertiaSlider = document.getElementById('inertiaSlider');
const inertiaValue = document.getElementById('inertiaValue');
const oscillationAmpSlider = document.getElementById('oscillationAmpSlider');
const oscillationAmpValue = document.getElementById('oscillationAmpValue');
const oscillationPeriodSlider = document.getElementById('oscillationPeriodSlider');
const oscillationPeriodValue = document.getElementById('oscillationPeriodValue');
const randomDisturbanceSlider = document.getElementById('randomDisturbanceSlider');
const randomDisturbanceValue = document.getElementById('randomDisturbanceValue');

// Performance metrics
const settlingTime = document.getElementById('settlingTime');
const overshoot = document.getElementById('overshoot');
const steadyError = document.getElementById('steadyError');

// State
let autoControl = false;
let simulationStartTime = null;
let maxTemperatureReached = 0;
let settlingDetected = false;
let settlingTimeValue = null;
let overshotDetected = false;
let overshootValue = null;

// Fetch state from server periodically
function fetchState() {
    fetch('/api/state')
        .then(response => response.json())
        .then(state => {
            updateUI(state);
        })
        .catch(error => console.error('Error fetching state:', error));
}

// Update UI based on state
function updateUI(state) {
    // Update temperature display
    currentTempDisplay.textContent = state.current_temp.toFixed(1) + '°C';
    targetTempDisplay.textContent = state.target_temp.toFixed(1) + '°C';
    
    // Update heater status
    if (state.heater_on) {
        heaterStatus.textContent = 'Heater ON';
        heaterStatus.classList.add('on');
        heaterStatus.classList.remove('off');
    } else {
        heaterStatus.textContent = 'Heater OFF';
        heaterStatus.classList.add('off');
        heaterStatus.classList.remove('on');
    }
    
    // Update auto control button
    if (state.auto_control) {
        autoToggle.textContent = 'Disable PID Control';
        autoControl = true;
    } else {
        autoToggle.textContent = 'Enable PID Control';
        autoControl = false;
    }
    
    // Update basic sliders
    targetSlider.value = state.target_temp;
    targetValue.textContent = state.target_temp.toFixed(1);
    
    // Update simulation speed slider
    if (state.time_speedup) {
        speedSlider.value = state.time_speedup;
        speedValue.textContent = state.time_speedup.toFixed(1);
    }
    
    // Update PID sliders
    kpSlider.value = state.pid.kp;
    kpValue.textContent = state.pid.kp.toFixed(1);
    
    kiSlider.value = state.pid.ki;
    kiValue.textContent = state.pid.ki.toFixed(2);
    
    kdSlider.value = state.pid.kd;
    kdValue.textContent = state.pid.kd.toFixed(2);
    
    // Update instability sliders if available
    if (state.instability) {
        // Only set these if the values exist to avoid overwriting user changes
        if (state.instability.control_delay !== undefined) {
            delaySlider.value = state.instability.control_delay;
            delayValue.textContent = state.instability.control_delay.toFixed(1);
        }
        if (state.instability.thermal_inertia !== undefined) {
            inertiaSlider.value = state.instability.thermal_inertia;
            inertiaValue.textContent = state.instability.thermal_inertia.toFixed(1);
        }
        if (state.instability.oscillation_amplitude !== undefined) {
            oscillationAmpSlider.value = state.instability.oscillation_amplitude;
            oscillationAmpValue.textContent = state.instability.oscillation_amplitude.toFixed(1);
        }
        if (state.instability.oscillation_period !== undefined) {
            oscillationPeriodSlider.value = state.instability.oscillation_period;
            oscillationPeriodValue.textContent = state.instability.oscillation_period.toFixed(1);
        }
        if (state.instability.random_max !== undefined) {
            randomDisturbanceSlider.value = state.instability.random_max;
            randomDisturbanceValue.textContent = state.instability.random_max.toFixed(1);
        }
    }
    
    // Update chart
    if (state.history && state.history.length > 0) {
        // Update temperature data with heater status
        tempChart.data.datasets[0].data = state.history.map(point => ({
            x: point.time,
            y: point.temperature,
            heaterOn: point.heater_on  // Include heater status for coloring
        }));
        
        // Update target line
        tempChart.data.datasets[1].data = state.history.map(point => ({
            x: point.time,
            y: point.target
        }));
        
        tempChart.update('none');  // Update without animation for smoother experience
        
        // Calculate performance metrics if auto control is on
        if (state.auto_control) {
            calculatePerformanceMetrics(state);
        }
    }
}

// Calculate performance metrics
function calculatePerformanceMetrics(state) {
    const target = state.target_temp;
    const current = state.current_temp;
    const history = state.history;
    
    // If this is the first time auto control is enabled, reset metrics
    if (!simulationStartTime && state.auto_control) {
        simulationStartTime = history[history.length - 1].time;
        maxTemperatureReached = current;
        settlingDetected = false;
        overshotDetected = false;
    }
    
    // Track maximum temperature for overshoot calculation
    if (current > maxTemperatureReached) {
        maxTemperatureReached = current;
    }
    
    // Calculate overshoot
    if (maxTemperatureReached > target && !overshotDetected) {
        overshootValue = ((maxTemperatureReached - target) / target * 100).toFixed(1);
        overshoot.textContent = overshootValue + '%';
        overshotDetected = true;
    }
    
    // Calculate settling time (when temperature stays within 5% of target)
    const settlingThreshold = target * 0.05; // 5% of target
    
    if (!settlingDetected) {
        // Check last 10 points to see if we've settled
        const lastPoints = history.slice(-10);
        const allWithinRange = lastPoints.every(point => 
            Math.abs(point.temperature - target) <= settlingThreshold
        );
        
        if (allWithinRange && lastPoints.length === 10) {
            settlingDetected = true;
            settlingTimeValue = (lastPoints[0].time - simulationStartTime).toFixed(1);
            settlingTime.textContent = settlingTimeValue + ' seconds';
        }
    }
    
    // Calculate steady-state error
    if (history.length > 20) {
        const lastPoints = history.slice(-20);
        const avgTemp = lastPoints.reduce((sum, point) => sum + point.temperature, 0) / lastPoints.length;
        const error = Math.abs(avgTemp - target).toFixed(2);
        steadyError.textContent = error + '°C';
    }
}

// Set up event listeners
heaterToggle.addEventListener('click', () => {
    // Only allow manual control if not in auto mode
    if (!autoControl) {
        fetch('/api/heater', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ on: heaterStatus.textContent.includes('OFF') })
        });
    }
});

autoToggle.addEventListener('click', () => {
    fetch('/api/auto_control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !autoControl })
    })
    .then(() => {
        // Reset metrics when toggling
        simulationStartTime = null;
        settlingTime.textContent = 'N/A';
        overshoot.textContent = 'N/A';
        steadyError.textContent = 'N/A';
    });
});

targetSlider.addEventListener('input', () => {
    const value = parseFloat(targetSlider.value);
    targetValue.textContent = value.toFixed(1);
    fetch('/api/target', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ temperature: value })
    });
});

kpSlider.addEventListener('input', () => {
    const value = parseFloat(kpSlider.value);
    kpValue.textContent = value.toFixed(1);
    updatePID();
});

kiSlider.addEventListener('input', () => {
    const value = parseFloat(kiSlider.value);
    kiValue.textContent = value.toFixed(2);
    updatePID();
});

kdSlider.addEventListener('input', () => {
    const value = parseFloat(kdSlider.value);
    kdValue.textContent = value.toFixed(2);
    updatePID();
});

function updatePID() {
    fetch('/api/pid', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            kp: parseFloat(kpSlider.value),
            ki: parseFloat(kiSlider.value),
            kd: parseFloat(kdSlider.value)
        })
    });
}

// Instability sliders event listeners
delaySlider.addEventListener('input', () => {
    const value = parseFloat(delaySlider.value);
    delayValue.textContent = value.toFixed(1);
    updateInstability();
});

inertiaSlider.addEventListener('input', () => {
    const value = parseFloat(inertiaSlider.value);
    inertiaValue.textContent = value.toFixed(1);
    updateInstability();
});

oscillationAmpSlider.addEventListener('input', () => {
    const value = parseFloat(oscillationAmpSlider.value);
    oscillationAmpValue.textContent = value.toFixed(1);
    updateInstability();
});

oscillationPeriodSlider.addEventListener('input', () => {
    const value = parseFloat(oscillationPeriodSlider.value);
    oscillationPeriodValue.textContent = value.toFixed(1);
    updateInstability();
});

randomDisturbanceSlider.addEventListener('input', () => {
    const value = parseFloat(randomDisturbanceSlider.value);
    randomDisturbanceValue.textContent = value.toFixed(1);
    updateInstability();
});

function updateInstability() {
    fetch('/api/instability', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            control_delay: parseFloat(delaySlider.value),
            thermal_inertia: parseFloat(inertiaSlider.value),
            oscillation_amplitude: parseFloat(oscillationAmpSlider.value),
            oscillation_period: parseFloat(oscillationPeriodSlider.value),
            random_max: parseFloat(randomDisturbanceSlider.value)
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Instability parameters updated');
            
            // Reset metrics after changing system parameters
            if (autoControl) {
                simulationStartTime = null;
                settlingTime.textContent = 'N/A';
                overshoot.textContent = 'N/A';
                steadyError.textContent = 'N/A';
            }
        }
    })
    .catch(error => console.error('Error updating instability parameters:', error));
}

resetInstability.addEventListener('click', () => {
    // Reset to default values
    delaySlider.value = 2.0;
    delayValue.textContent = '2.0';
    
    inertiaSlider.value = 3.0;
    inertiaValue.textContent = '3.0';
    
    oscillationAmpSlider.value = 1.0;
    oscillationAmpValue.textContent = '1.0';
    
    oscillationPeriodSlider.value = 5.0;
    oscillationPeriodValue.textContent = '5.0';
    
    randomDisturbanceSlider.value = 1.5;
    randomDisturbanceValue.textContent = '1.5';
    
    // Update the server
    updateInstability();
});

openDoor.addEventListener('click', () => {
    fetch('/api/disturbance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'door_open' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(data.message);
            // Reset metrics when disturbance is applied
            if (autoControl) {
                simulationStartTime = null;
                settlingTime.textContent = 'N/A';
                overshoot.textContent = 'N/A';
                steadyError.textContent = 'N/A';
            }
        }
    })
    .catch(error => console.error('Error applying disturbance:', error));
});

speedSlider.addEventListener('input', () => {
    const value = parseFloat(speedSlider.value);
    speedValue.textContent = value.toFixed(1);
    fetch('/api/simulation_speed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speedup: value })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`Simulation speed set to ${data.time_speedup}×`);
        }
    })
    .catch(error => console.error('Error setting simulation speed:', error));
});

// Start periodic updates
setInterval(fetchState, 500);