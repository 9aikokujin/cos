import API from "@/app/api";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { useVideosStore } from "@/app/store/entity/store";

import Loader from "@/components/loader/Loader";
import VideoItem from "./components/VideoItem";

import "./VideosList.css";

const fetchVideos = async (page, term) => {
  if (!term) {
    const response = await API.video.getVideos({ page });
    return response;
  } else {
    const response = await API.video.getVideos({ page, link: term });
    return response;
  }
};

const VideosList = () => {
  const { items, isLoading, lastItemRef } = useInfiniteScroll(useVideosStore, fetchVideos, "videos");
  return (
    <div className="_flex_col_center" style={{ gap: 20, overflow: "auto", paddingBottom: 20 }}>
      {items.map((item, i) => (
        <VideoItem key={item.id} ref={i === items.length - 1 ? lastItemRef : null} video={item} />
      ))}
      {isLoading && <Loader />}
    </div>
  );
};

export default VideosList;
