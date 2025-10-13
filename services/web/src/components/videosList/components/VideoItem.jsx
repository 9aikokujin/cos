import { ButtonIcon, Button } from "@/shared/ui/button/Button";
import { useConfirmModal } from "@/hooks/useConfirmModal";

const VideoItem = () => {
  const { confirmAction } = useConfirmModal();

  const handleDeleteConfirm = () => {
    console.log("✅ Удаление видео");
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
    <div className="video_item _flex">
      <div className="video_image">
        <img src="" alt="" />
      </div>
      <div className="video_info _flex_col">
        <h3 className="_name">База под макияж с SPF 50 от Cosmeya</h3>
        <p className="_url">https://www.youtube.com/watch?v=MYTP3456</p>
        <div className="video_item_btns _flex_sb">
          <ButtonIcon onClick={handleDelete} name={"trash"} />
          <Button className={"_orange _detail_btn"}>Детально</Button>
        </div>
      </div>
    </div>
  );
};

export default VideoItem;
