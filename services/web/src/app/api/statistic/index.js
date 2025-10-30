export default (instance) => ({
  getStatistic({
    id,
    date_to,
    date_from,
    video_id,
    channel_id,
    channel_type,
    user_ids,
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
        user_ids,
        date_published_to,
        date_published_from,
      },
      paramsSerializer: {
        indexes: null,
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
    user_ids,
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
        user_ids,
        date_published_to,
        date_published_from,
      },
      paramsSerializer: {
        indexes: null,
      },
    }).then((response) => response.data);
  },
  getCountPublishedVideo(params) {
    const allowedKeys = ["date_to", "date_from", "channel_id", "channel_type", "user_ids"];
    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(
        ([key, v]) => allowedKeys.includes(key) && v !== "" && v !== null && v !== undefined
      )
    );
    return instance({
      method: "GET",
      url: "/videohistory/daily_count_all",
      params: cleanParams,
      paramsSerializer: {
        indexes: null,
      },
    }).then((response) => response.data);
  },
  getCountPublishedVideoWithTags(params, tags) {
    const allowedKeys = ["date_to", "date_from", "channel_id", "channel_type", "user_ids"];
    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(
        ([key, v]) => allowedKeys.includes(key) && v !== "" && v !== null && v !== undefined
      )
    );
    return instance({
      method: "GET",
      url: "/videohistory/daily_article_count",
      params: {...cleanParams, articles: tags},
      paramsSerializer: {
        indexes: null,
      },
    }).then((response) => response.data);
  },
  getVideoHistory(params) {
    const allowedKeys = [
      "id",
      "date_to",
      "date_from",
      "video_id",
      "channel_id",
      "channel_type",
      "user_ids",
    ];
    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(
        ([key, v]) => allowedKeys.includes(key) && v !== "" && v !== null && v !== undefined
      )
    );
    return instance({
      method: "GET",
      url: "/videohistory/",
      params: cleanParams,
      paramsSerializer: {
        indexes: null,
      },
    }).then((response) => response.data);
  },
  downloadReport(params) {
    const allowedKeys = ["date_to", "date_from", "channel_type", "user_ids"];
    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(
        ([key, v]) => allowedKeys.includes(key) && v !== "" && v !== null && v !== undefined
      )
    );
    return instance({
      method: "GET",
      url: "/videohistory/download_stats_csv",
      params: cleanParams,
      paramsSerializer: {
        indexes: null,
      },
    }).then((response) => response.data);
  },
});
