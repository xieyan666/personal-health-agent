import { EditOutlined } from "@ant-design/icons";
import {
  Button,
  Card,
  Col,
  Empty,
  InputNumber,
  Modal,
  Row,
  Select,
  Tabs,
  Tag,
  message,
} from "antd";
import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts";
import {
  getHealthProfile,
  getHealthSummary,
  getHealthTrends,
  updateHealthProfile,
  type HealthProfile,
} from "../../api/healthProfile";
import "./profile.css";

function Chart({ option }: { option: echarts.EChartsOption }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const c = echarts.init(ref.current);
    c.setOption(option);
    const r = () => c.resize();
    window.addEventListener("resize", r);
    return () => {
      window.removeEventListener("resize", r);
      c.dispose();
    };
  }, [option]);
  return <div ref={ref} style={{ height: 280, width: "100%" }} />;
}
const axis = {
  axisLabel: { color: "#7d91aa" },
  axisLine: { lineStyle: { color: "#dce7e2" } },
};
export function Profile() {
  const [profile, setProfile] = useState<HealthProfile | null>(null),
    [summary, setSummary] = useState<any>(),
    [trends, setTrends] = useState<any>({
      sleep: [],
      exercise: [],
      heart_rate: [],
    }),
    [days, setDays] = useState(30),
    [editing, setEditing] = useState(false),
    [saving, setSaving] = useState(false),
    [draft, setDraft] = useState<any>({});
  const load = async () => {
    try {
      const [p, t, s] = await Promise.all([
        getHealthProfile(),
        getHealthTrends({ days }),
        getHealthSummary(),
      ]);
      setProfile(p);
      // 后端按 days 查询；同时按当前范围保护展示，避免旧 API/缓存返回更长数据。
      setTrends({ sleep: t.sleep.slice(-days), exercise: t.exercise.slice(-days), heart_rate: t.heart_rate.slice(-days) });
      setSummary(s);
      setDraft({
        age: p.age ?? undefined,
        gender: p.gender ?? undefined,
        height: p.height ?? undefined,
        weight: p.weight ?? undefined,
      });
    } catch {
      message.error("健康档案加载失败");
    }
  };
  useEffect(() => {
    void load();
  }, [days]);
  const save = async () => {
    setSaving(true);
    try {
      const p = await updateHealthProfile(draft);
      setProfile(p);
      setEditing(false);
      message.success("健康档案已保存");
    } catch {
      message.error("保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  };
  const val = (v: any) => (v == null || v === "" ? "暂无数据" : v);
  const dates = (a: any[]) => a.map((x) => x.date.slice(5));
  const sleepOpt: echarts.EChartsOption = {
    color: ["#18a957"],
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: dates(trends.sleep), ...axis },
    yAxis: { type: "value", name: "小时", ...axis },
    series: [
      {
        type: "line",
        smooth: true,
        data: trends.sleep.map((x: any) => x.sleep_duration),
        areaStyle: { opacity: 0.12 },
      },
    ],
  };
  const exerciseOpt: echarts.EChartsOption = {
    color: ["#18a957", "#8bd3a7"],
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: dates(trends.exercise), ...axis },
    yAxis: [
      { type: "value", name: "分钟", ...axis },
      { type: "value", name: "步数", ...axis },
    ],
    series: [
      {
        type: "line",
        name: "运动时间",
        data: trends.exercise.map((x: any) => x.duration),
      },
      {
        type: "bar",
        yAxisIndex: 1,
        name: "步数",
        data: trends.exercise.map((x: any) => x.steps),
      },
    ],
  };
  const hrOpt: echarts.EChartsOption = {
    color: ["#f0a33a"],
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: dates(trends.heart_rate), ...axis },
    yAxis: { type: "value", name: "bpm", ...axis },
    series: [
      {
        type: "line",
        smooth: true,
        data: trends.heart_rate.map((x: any) => x.average),
      },
    ],
  };
  const status = (type: string, v: any) => {
    if (v == null) return <Tag>暂无数据</Tag>;
    const good =
      type === "bmi"
        ? v >= 18.5 && v < 24
        : type === "sleep"
          ? v >= 7
          : type === "hr"
            ? v >= 60 && v <= 90
            : v >= 150;
    return (
      <Tag color={good ? "success" : "warning"}>
        {good ? "正常" : "需要关注"}
      </Tag>
    );
  };
  return (
    <section className="profile-page">
      <div className="profile-heading">
        <div><p>我的个人健康数字画像</p></div>
        <Button type="primary" icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑档案</Button>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="我的基本信息" className="profile-card">
            <div className="profile-grid">
              <span>用户账号</span>
              <strong>{profile?.username || "暂无数据"}</strong>
              <span>年龄</span>
              <strong>
                {val(profile?.age)}
                {profile?.age ? " 岁" : ""}
              </strong>
              <span>性别</span>
              <strong>{val(profile?.gender)}</strong>
              <span>身高</span>
              <strong>
                {val(profile?.height)}
                {profile?.height ? " cm" : ""}
              </strong>
              <span>体重</span>
              <strong>
                {val(profile?.weight)}
                {profile?.weight ? " kg" : ""}
              </strong>
              <span>BMI</span>
              <strong>
                {val(profile?.bmi)} {status("bmi", profile?.bmi)}
              </strong>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="当前健康指标" className="profile-card">
            <div className="metric-grid">
              {[
                ["BMI", profile?.bmi, "Health Profile", "bmi"],
                ["睡眠", summary?.sleep?.avg_sleep, "Wearable", "sleep"],
                [
                  "运动",
                  summary?.exercise?.avg_duration,
                  "Wearable",
                  "exercise",
                ],
                ["心率", summary?.heart_rate?.avg_hr, "Wearable", "hr"],
              ].map(([l, v, s, t]) => (
                <div className="metric-card" key={l as string}>
                  <span>{l as string}</span>
                  <strong>{val(v)}</strong>
                  {status(t as string, v)}
                  <Tag>{s as string}</Tag>
                </div>
              ))}
            </div>
          </Card>
        </Col>
        <Col span={24}>
          <Card title={<div className="trend-card-title"><span>健康趋势</span><div className="trend-range"><span>时间范围</span><Select size="small" value={days} onChange={setDays} options={[{ value: 7, label: '近7天' }, { value: 15, label: '近15天' }, { value: 30, label: '近30天' }, { value: 60, label: '近60天' }]} /></div></div>} className="profile-card">
            <Tabs
              items={[
                {
                  key: "sleep",
                  label: "睡眠趋势",
                  children: trends.sleep.length ? (
                    <Chart option={sleepOpt} />
                  ) : (
                    <Empty description="暂无睡眠数据" />
                  ),
                },
                {
                  key: "exercise",
                  label: "运动趋势",
                  children: trends.exercise.length ? (
                    <Chart option={exerciseOpt} />
                  ) : (
                    <Empty description="暂无运动数据" />
                  ),
                },
                {
                  key: "heart",
                  label: "心率趋势",
                  children: trends.heart_rate.length ? (
                    <Chart option={hrOpt} />
                  ) : (
                    <Empty description="暂无心率数据" />
                  ),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
      <Modal
        title="编辑健康档案"
        open={editing}
        onCancel={() => setEditing(false)}
        onOk={() => void save()}
        confirmLoading={saving}
      >
        <div className="profile-form">
          <label>
            年龄
            <InputNumber
              min={0}
              max={150}
              value={draft.age}
              onChange={(v) => setDraft({ ...draft, age: v ?? undefined })}
            />
          </label>
          <label>
            性别
            <Select
              allowClear
              value={draft.gender}
              options={[
                { value: "male", label: "男" },
                { value: "female", label: "女" },
                { value: "other", label: "其他" },
              ]}
              onChange={(v) => setDraft({ ...draft, gender: v })}
            />
          </label>
          <label>
            身高（cm）
            <InputNumber
              min={1}
              value={draft.height}
              onChange={(v) => setDraft({ ...draft, height: v ?? undefined })}
            />
          </label>
          <label>
            体重（kg）
            <InputNumber
              min={1}
              value={draft.weight}
              onChange={(v) => setDraft({ ...draft, weight: v ?? undefined })}
            />
          </label>
        </div>
      </Modal>
    </section>
  );
}
