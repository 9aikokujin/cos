import VideosList from "@/components/videosList/VideosList";
import Filter from "@/components/filter/Filter";
import SearchInput from "@/components/searchInput/SearchInput";

const VideosPage = () => {
  return (
    <div className="container">
      <div className="_flex_sb" style={{ gap: 11, marginBottom: 12 }}>
        <Filter />
        <SearchInput />
      </div>
      <VideosList />
    </div>
  );
};

export default VideosPage;
