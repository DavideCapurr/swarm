import { IntrusionResponseDemo } from "@/components/intrusion-demo/IntrusionResponseDemo";

export const metadata = {
  title: "SWARM · Intrusion response demo",
  description: "Camera detection, fleet decision and bounded response demo.",
};

export default function IntrusionDemoPage() {
  return <IntrusionResponseDemo />;
}
