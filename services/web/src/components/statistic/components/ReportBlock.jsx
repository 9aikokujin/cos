import { Button } from "@/shared/ui/button/Button";
import { useDragScroll } from "@/hooks/useDragScroll";
import dayjs from "dayjs";

const video = [
  {
    id: 1,
    name: "Распаковка нового iPhone 16 Pro",
    published_date: "2025-10-15",
    products: [
      { id: 101, title: "iPhone 16 Pro 256GB" },
      { id: 102, title: "Apple Silicone Case" },
    ],
  },
  {
    id: 2,
    name: "Обзор на MacBook Air M4",
    published_date: "2025-09-28",
    products: [
      { id: 103, title: "MacBook Air M4 13”" },
    ],
  },
  {
    id: 3,
    name: "Как выбрать наушники для тренировок",
    published_date: "2025-09-10",
    products: [], // нет товаров
  },
  {
    id: 4,
    name: "Новый iPad Pro 2025 — впечатления",
    published_date: "2025-08-30",
    products: [
      { id: 104, title: "iPad Pro 12.9” 2025" },
      { id: 105, title: "Apple Pencil 3" },
    ],
  },
  {
    id: 5,
    name: "Распаковка нового iPhone 16 Pro",
    published_date: "2025-10-15",
    products: [
      { id: 101, title: "iPhone 16 Pro 256GB" },
      { id: 102, title: "Apple Silicone Case" },
    ],
  },
  {
    id: 6,
    name: "Обзор на MacBook Air M4",
    published_date: "2025-09-28",
    products: [
      { id: 103, title: "MacBook Air M4 13”" },
    ],
  },
  {
    id: 7,
    name: "Как выбрать наушники для тренировок",
    published_date: "2025-09-10",
    products: [], // нет товаров
  },
  {
    id: 8,
    name: "Новый iPad Pro 2025 — впечатления",
    published_date: "2025-08-30",
    products: [
      { id: 104, title: "iPad Pro 12.9” 2025" },
      { id: 105, title: "Apple Pencil 3" },
    ],
  },
  {
    id: 9,
    name: "Распаковка нового iPhone 16 Pro",
    published_date: "2025-10-15",
    products: [
      { id: 101, title: "iPhone 16 Pro 256GB" },
      { id: 102, title: "Apple Silicone Case" },
    ],
  },
  {
    id: 10,
    name: "Обзор на MacBook Air M4",
    published_date: "2025-09-28",
    products: [
      { id: 103, title: "MacBook Air M4 13”" },
    ],
  },
  {
    id: 11,
    name: "Как выбрать наушники для тренировок",
    published_date: "2025-09-10",
    products: [], // нет товаров
  },
  {
    id: 12,
    name: "Новый iPad Pro 2025 — впечатления",
    published_date: "2025-08-30",
    products: [
      { id: 104, title: "iPad Pro 12.9” 2025" },
      { id: 105, title: "Apple Pencil 3" },
    ],
  },
];


const ReportBlock = () => {
  const { containerRef, isDragging, handleMouseDown, handleMouseMove, handleMouseUp } =
  useDragScroll();
  return (
    <div className="report_container">
      <div className="_flex_sb_center" style={{marginBottom: 20}}>
        <h3 className="_title">Отчет</h3>
        <Button className={"_orange report_download_btn"}>Скачать</Button>
      </div>
      <div className="statistic__video_table">
          <div
            className="table_container"
            ref={containerRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <table className="table">
              <thead>
                <tr>
                  <th>Видео</th>
                  <th>Товар</th>
                  <th>Дата привязки</th>
                </tr>
              </thead>
              <tbody>
                {video.map((videoItem) => {
                  if (!videoItem.products || videoItem.products.length === 0) {
                    return (
                      <tr key={`${videoItem.id}-no-product`}>
                        <td data-label="Видео">
                          <span>{videoItem.name}</span>
                        </td>
                        <td data-label="Товар">
                          <span className="text-muted">Товар еще не привязан</span>
                        </td>
                        <td data-label="Дата привязки">
                          <span>{dayjs(videoItem.published_date).format('DD.MM.YYYY') || ""}</span>
                        </td>
                      </tr>
                    );
                  }

                  return videoItem.products.map((product, index) => (
                    <tr key={`${videoItem.id}-${product.id}-${index}`}>
                      <td data-label="Видео">
                        <span>{videoItem?.name}</span>
                      </td>
                      <td data-label="Товар">
                        <span>{product?.title}</span>
                      </td>
                      <td data-label="Дата привязки">
                        <span>{dayjs(videoItem.published_date).format('DD.MM.YYYY') || ""}</span>
                      </td>
                    </tr>
                  ));
                })}
              </tbody>
            </table>
          </div>
        </div>
    </div>
  );
};

export default ReportBlock;
