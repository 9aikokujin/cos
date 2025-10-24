import { memo } from "react";
import { useNavigate } from "react-router-dom";

import { useConfirmModal } from "@/hooks/useConfirmModal";
import { AppRoutes } from "@/app/routes/routes";
import { useVideosStore } from "@/app/store/entity/store";

import { ButtonIcon, Button } from "@/shared/ui/button/Button";
import ImageWithFallback from "@/shared/ui/imageWithFallback/ImageWithFallback";

const VideoItem = memo(({ video, ref }) => {
  const { confirmAction } = useConfirmModal();
  const navigate = useNavigate();
  const { removeItem } = useVideosStore();

  const handleDeleteConfirm = async () => {
    await API.video.deleteVideo(video.id);
    removeItem(video.id);
  };

  const handleDelete = () => {
    confirmAction({
      title: "Удаление видео",
      description: "Вы уверены, что хотите удалить видео?",
      btnTitle: "Удалить",
      onConfirm: handleDeleteConfirm,
    });
  };

  const handleNavigate = (filterKey, value) => {
    navigate(AppRoutes.STATISTIC, { state: { filterKey, value } });
  };

  return (
    <div ref={ref} className="video_item _flex">
      <div className="video_image">
        <ImageWithFallback src={video?.image} alt={video?.name} className="" />
      </div>
      <div className="video_info _flex_col">
        <h3 className="_name">{video.name}</h3>
        <p className="_url">{video.link}</p>
        <div className="video_item_btns _flex_sb">
          <ButtonIcon onClick={handleDelete} name={"trash"} />
          <Button
            onClick={() => handleNavigate("setFilterVideoId", video?.id)}
            className={"_orange _detail_btn"}
          >
            Детально
          </Button>
        </div>
      </div>
    </div>
  );
});

export default VideoItem;
