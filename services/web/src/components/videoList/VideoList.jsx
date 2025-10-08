import VideoItem from "@/components/videoItem/VideoItem";

import "./VideoList.css";

const VideoList = ({ video, lastItemRef }) => {
  return (
    <div className="video__list">
      {video.map((item, index) => {
        if (video.length === index + 1) {
          return <VideoItem key={item.id} item={item} ref={lastItemRef} />;
        }
        return <VideoItem key={item.id} item={item} />;
      })}
    </div>
  );
};

export default VideoList;
