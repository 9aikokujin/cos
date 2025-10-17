import { useVideosStore } from "@/app/store/entity/store";
import { useResetFiltersOnLeave } from "@/hooks/useResetFiltersOnLeave";

import VideosList from "@/components/videosList/VideosList";
import Filter from "@/components/filter/Filter";
import SearchInput from "@/components/searchInput/SearchInput";

const VideosPage = () => {
  useResetFiltersOnLeave()
  return (
    <div className="container">
      <div className="_flex_sb" style={{ gap: 11, marginBottom: 12 }}>
        <Filter />
        <SearchInput store={useVideosStore} />
      </div>
      <VideosList />
    </div>
  );
};

export default VideosPage;
