import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

import { Line } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const date = ["14 Oct", "15 Oct", "16 Oct", "17 Oct", "18 Oct", "19 Oct", "20 Oct"];

const views = [120, 180, 90, 220, 160, 250, 300];

const Diagram = () => {
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
  return (
    <div className="diagram__container">
      <Line key={JSON.stringify(data)} data={data} options={options} />
    </div>
  );
};

export default Diagram;
