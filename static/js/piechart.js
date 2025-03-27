const chartDom3 = document.getElementById("chart3");
const myChart3 = echarts.init(chartDom3);

fetch("/api/sentiment_breakdown")
    .then(response => response.json())
    .then(data => {
        const totalValue = data.reduce((sum, item) => sum + item.value, 0);

        const option3 = {
            tooltip: { trigger: "item" },
            legend: { show: true, bottom: 0 },
            series: [
                {
                    name: "Data Breakdown",
                    type: "pie",
                    radius: ["25%", "55%"],
                    avoidLabelOverlap: false,
                    label: {
                        show: true,
                        position: "outside",
                        formatter: "{c} ({d}%)",
                        fontSize: 14,
                        fontWeight: "normal",
                    },
                    emphasis: {
                        label: {
                            show: true,
                            fontSize: 16,
                            fontWeight: "normal",
                        },
                    },
                    labelLine: { show: true },
                    itemStyle: {
                        color: function (params) {
                            const colors = ["#7086FD", "#6FD195", "#FFAE4C"];
                            return colors[params.dataIndex];
                        },
                    },
                    data: data,
                },
            ],
            graphic: {
                type: "text",
                left: "center",
                top: "center",
                style: {
                    text: totalValue,
                    fontSize: 20,
                    fontWeight: "bold",
                    fill: "#333",
                },
            },
        };

        myChart3.setOption(option3);
    })
    .catch(error => {
        console.error("Error fetching sentiment data:", error);
    });

window.addEventListener("resize", function () {
    myChart3.resize();
});
