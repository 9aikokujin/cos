import { useLocation, useParams } from "react-router-dom";
import { useEffect, useLayoutEffect, useState } from "react";

import { useVideosStore } from "@/app/store/entity/store";
import { useFilterStore } from "@/app/store/filter/store";
import { useResetFiltersOnLeave } from "@/hooks/useResetFiltersOnLeave";

import VideosList from "@/components/videosList/VideosList";
import Filter from "@/components/filter/Filter";
import SearchInput from "@/components/searchInput/SearchInput";

const VideosPage = () => {
  const { id } = useParams();
  console.log(id);
  const { pathname } = useLocation();
  const setUsertId = useFilterStore((state) => state.setFilterUserId);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!id) {
      setIsLoading(false);
    } else {
      setUsertId(id);
      setIsLoading(false);
    }
  }, [id, pathname]);

  useResetFiltersOnLeave();

  return isLoading ? (
    <></>
  ) : (
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
