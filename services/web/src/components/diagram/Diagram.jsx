import { Line } from "react-chartjs-2";
import { Chart as ChartJS } from "chart.js/auto";

import "./Diagram.css";

const Diagram = ({ views, date }) => {
  const newViews = {
    views: views.map((v, i) => (i === 0 ? v : v - views[i - 1])),
  };
  const data = {
    labels: date,
    datasets: [
      {
        label: "",
        data: views,
        borderColor: "rgb(75, 192, 192)",
        borderWidth: 0.35,
        tension: 0.1,
        pointBackgroundColor: "#fff",
        pointBorderColor: "rgb(75, 192, 192)",
        pointHoverBackgroundColor: "rgb(75, 192, 192)",
        pointHoverBorderColor: "#fff",
        pointBorderWidth: 1,
        pointRadius: 3,
      },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
    },
  };
  console.log(views);
  console.log(newViews);
  return (
    <>
      <div className="diagram__container">
        <Line data={data} options={options} />
      </div>
    </>
  );
};

export default Diagram;
