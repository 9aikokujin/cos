import { useEffect, useState } from "react";

import API from "@/app/api";
import { useFilterStore } from "@/app/store/filter/store";
import { useDragScroll } from "@/hooks/useDragScroll";

import Loader from "@/components/loader/Loader";

import { getLatestVideos } from "@/shared/utils/utils";


const TableVideo = () => {
  const { containerRef, handleMouseDown, handleMouseMove, handleMouseUp } =
    useDragScroll();
  const { filter } = useFilterStore();

  const [videoHistory, setVideoHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const fetchVideoHistory = async () => {
      setIsLoading(true);
      const data = await API.statistic.getVideoHistory({
        ...filter,
      });
      setVideoHistory(data);
      setIsLoading(false);
    };
    fetchVideoHistory();
  }, [filter]);
  return isLoading ? (
    <Loader />
  ) : (
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
              <th>Просмотры</th>
              <th>Комментарии</th>
              <th>Лайки</th>
            </tr>
          </thead>
          <tbody>
            {getLatestVideos(videoHistory).map((videoItem) => {
              return (
                <tr key={`${videoItem.id}-no-product`}>
                  <td data-label="Видео">
                    <span>{videoItem.video_name}</span>
                  </td>
                  <td data-label="Просмотры">
                    <span className="text-muted">{videoItem.amount_views}</span>
                  </td>
                  <td data-label="Комментарии">
                    <span>{videoItem.amount_comments}</span>
                  </td>
                  <td data-label="Лайки">
                    <span>{videoItem.amount_likes}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TableVideo;
