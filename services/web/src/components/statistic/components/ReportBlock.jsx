import API from "@/app/api";
import { useConfirmModal } from "@/hooks/useConfirmModal";
import { useFilterStore } from "@/app/store/filter/store";

import { Button } from "@/shared/ui/button/Button";
import TableVideo from "./TableVideo";


const ReportBlock = () => {
  const { confirmAction } = useConfirmModal();
  const {filter} = useFilterStore();

  const handleDownloadConfirm = async () => {
    const res = await API.statistic.downloadReport(filter);
    // Создаем Blob из полученных данных
    const blob = new Blob([res], { type: "text/csv;charset=utf-8;" });

    // Создаем ссылку для скачивания
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "statistics.csv");
    document.body.appendChild(link);
    link.click();

    // Очищаем память
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleDownload = () => {
    confirmAction({
      title: "Скачать отчет",
      description: "Вы уверены, что хотите скачать отчет?",
      btnTitle: "Скачать",
      onConfirm: handleDownloadConfirm,
    });
  };

  return (
    <div className="report_container">
      <div className="_flex_sb_center" style={{ marginBottom: 20 }}>
        <h3 className="_title">Отчет</h3>
        <Button onClick={handleDownload} className={"_orange report_download_btn"}>
          Скачать
        </Button>
      </div>
      <TableVideo />
    </div>
  );
};

export default ReportBlock;
