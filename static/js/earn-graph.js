const ctx = document.getElementById('lineChart').getContext('2d');

        const data = {
            labels: ['November', 'December', 'January','November', 'December', 'January'],
            datasets: [
                {
                    label: 'Line 1',
                    data: [1, 40, 50, 48, 60,70,50, 80],
                    borderColor: '#20C997',
                    fill: false,
                    lineTension: 0.1,
                    borderWidth: 3,
                    pointRadius: 1, 
                },
                {
                    label: 'Line 2',
                    data: [1, 48, 20, 30,55],
                    borderColor: '#8328BC', 
                    fill: false,
                    lineTension: 0.1,
                    borderWidth: 3,
                    pointRadius: 1 
                },
                {
                    label: 'Line 3',
                    data: [1, 30, 90,66,44,55],
                    borderColor: '#F5F85C', 
                    fill: false,
                    lineTension: 0.1,
                    borderWidth: 3,
                    pointRadius: 1
                }
            ]
        };

        const config = {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                scales: {
                    x: {
                        display: false 
                    },
                    y: {
                        display: false 
                    }
                },
                plugins: {
                    legend: {
                        display: false 
                    },
                    tooltip: {
                        enabled: false 
                    }
                }
            }
        };

        // Create the chart
        new Chart(ctx, config);