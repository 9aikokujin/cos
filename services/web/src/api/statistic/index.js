export default (instance) => ({
  getStatisctic({
    id,
    group_by,
    hashtag,
    channel_id,
    channel_type,
    date_from,
    date_to,
    video_url,
  }) {
    return instance({
      method: "GET",
      url: `analytics/analytics`,
      params: {
        user_id: id,
        group_by: group_by ? group_by : "day",
        hashtag: hashtag,
        channel_id: channel_id,
        channel_type: channel_type,
        date_from: date_from,
        date_to: date_to,
        video_url: video_url,
      },
      paramsSerializer: {
        indexes: null,
      },
    }).then((response) => response.data);
  },
  getHashTags(user_id) {
    return instance({
      method: "GET",
      url: "analytics/hashtags",
      params: {
        user_id,
      },
    }).then((response) => response.data);
  },
});
