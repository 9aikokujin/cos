import API from "@/app/api";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { useVideosStore } from "@/app/store/entity/store";

import Loader from "@/components/loader/Loader";
import VideoItem from "./components/VideoItem";

import "./VideosList.css";

const fetchVideos = async (page, term, filter) => {
  const params = { page };

  if (term) {
    // params.link = term;
    params.name = term;
  }

  if (filter?.channel_type) {
    params.type = filter.channel_type.toLowerCase();
  }

  if (filter?.user_ids) {
    params.user_id = filter.user_ids;
  }

  const response = await API.video.getVideos(params);
  return response;
};

const VideosList = () => {
  const { items, isLoading, lastItemRef } = useInfiniteScroll(
    useVideosStore,
    fetchVideos,
    "videos"
  );
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
