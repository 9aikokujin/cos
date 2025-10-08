import { useFilter } from "@/store/FilterAnalitic/main";
import "./VideoItem.css";
import { Link } from "react-router-dom";

const VideoItem = ({ item, ref }) => {
  const {
    actions: { setVideoUrl },
  } = useFilter();

  return (
    <Link
      ref={ref}
      to={"/diagram"}
      onClick={() => {
        setVideoUrl(item.link);
      }}
      className="video__item _flex_column"
    >
      <p className="video__name">{item.name}</p>
      <p className="video__link _flex">{item.link}</p>
    </Link>
  );
};

export default VideoItem;
