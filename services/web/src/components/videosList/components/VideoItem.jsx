import { memo } from "react";

import { ButtonIcon, Button } from "@/shared/ui/button/Button";
import { useConfirmModal } from "@/hooks/useConfirmModal";

const VideoItem = memo(({ video, ref }) => {
  const { confirmAction } = useConfirmModal();

  const handleDeleteConfirm = async () => {
    await API.video.deleteVideo(video.id);
    closeModal();
  };

  const handleDelete = () => {
    confirmAction({
      title: "Удаление видео",
      description: "Вы уверены, что хотите удалить видео?",
      onConfirm: handleDeleteConfirm,
    });
  };
  return (
    <div ref={ref} className="video_item _flex">
      <div className="video_image">
        {/* image === null в случае отсутствия изображения */}
        <img src={`https://cosmeya.dev-klick.cyou/api/v1/${video?.image}`} alt="" />
      </div>
      <div className="video_info _flex_col">
        <h3 className="_name">{video.name}</h3>
        <p className="_url">{video.link}</p>
        <div className="video_item_btns _flex_sb">
          <ButtonIcon onClick={handleDelete} name={"trash"} />
          <Button className={"_orange _detail_btn"}>Детально</Button>
        </div>
      </div>
    </div>
  );
});

export default VideoItem;
