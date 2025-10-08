import PageHeader from "@/components/pageHeader/PageHeader";
import VideoList from "@/components/videoList/VideoList";

import API from "@/api";
import { useAuth } from "@/store/AuthStore/main";
import { useScrollWithSearch } from "@/hooks/useScrollAndSearch";
import { useInput } from "@/hooks/useInput";

const VideoListPage = () => {
  const { token, user } = useAuth();
  const { debouncedValue, value, setValue } = useInput("", 300);

  const fetchVideoList = async ({ page, size, search }) => {
    const res = await API.video.getAll({
      token,
      id: user.role !== "admin" ? user.id : null,
      page,
      size,
      link: search ? search : null,
    });
    return {
      items: res.videos,
      pagination: res.pagination,
    };
  };

  const {
    items: videoList,
    setLastItemRef,
    refetch,
  } = useScrollWithSearch({
    fetchFn: fetchVideoList,
    searchTerm: debouncedValue,
    pageSize: 10,
  });

  return (
    <>
      <PageHeader
        isShowBtns={true}
        type={"video"}
        onSearch={setValue}
        term={value}
        reset={refetch}
      />
      <VideoList video={videoList} lastItemRef={setLastItemRef} />
    </>
  );
};

export default VideoListPage;
