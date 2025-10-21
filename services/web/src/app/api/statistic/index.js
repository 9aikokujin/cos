export default (instance) => ({
  getStatistic({
    id,
    date_to,
    date_from,
    video_id,
    channel_id,
    channel_type,
    user_id,
    date_published_to,
    date_published_from,
  }) {
    return instance({
      method: "GET",
      url: "/videohistory/filtered_stats_all",
      params: {
        id,
        date_to,
        date_from,
        video_id,
        channel_id,
        channel_type,
        user_id,
        date_published_to,
        date_published_from,
      },
    }).then((response) => response.data);
  },
  getStatisticWithTags({
    articles,
    id,
    date_to,
    date_from,
    video_id,
    channel_id,
    channel_type,
    user_id,
    date_published_to,
    date_published_from,
  }) {
    return instance({
      method: "GET",
      url: "/videohistory/filtered_stats_art",
      params: {
        articles,
        id,
        date_to,
        date_from,
        video_id,
        channel_id,
        channel_type,
        user_id,
        date_published_to,
        date_published_from,
      },
    }).then((response) => response.data);
  },
  getCountPublishedVideo(params) {
    const allowedKeys = ["date_to", "date_from", "channel_id", "channel_type", "user_id"];
    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(
        ([key, v]) => allowedKeys.includes(key) && v !== "" && v !== null && v !== undefined
      )
    );
    return instance({
      method: "GET",
      url: "/videohistory/daily_count_all",
      params: cleanParams,
    }).then((response) => response.data);
  },
  getCountPublishedVideoWithTags(params) {
    const allowedKeys = ["date_to", "date_from", "channel_id", "channel_type", "user_id"];
    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(
        ([key, v]) => allowedKeys.includes(key) && v !== "" && v !== null && v !== undefined
      )
    );
    return instance({
      method: "GET",
      url: "/videohistory/daily_article_count",
      params: cleanParams,
    }).then((response) => response.data);
  },
});
