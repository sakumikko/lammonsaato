import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '@/components/ui/card';
import { Zap, Euro, PiggyBank, Thermometer } from 'lucide-react';
import { AnalyticsSummary } from '@/types/analytics';

interface SummaryCardsProps {
  summary: AnalyticsSummary;
}

export function SummaryCards({ summary }: SummaryCardsProps) {
  const { t } = useTranslation();

  const cards = [
    {
      icon: Zap,
      label: t('analytics.summary.totalEnergy'),
      value: `${summary.totalElectricEnergy.toFixed(1)} kWh`,
      subValue: `${summary.totalThermalEnergy.toFixed(1)} kWh ${t('analytics.charts.energyThermal').toLowerCase()}`,
      color: 'text-primary',
      bgColor: 'bg-primary/10',
    },
    {
      icon: Euro,
      label: t('analytics.summary.totalCost'),
      value: `€${summary.totalCost.toFixed(2)}`,
      subValue: `${t('analytics.summary.avgPrice')}: ${(summary.totalCost / summary.totalElectricEnergy * 100).toFixed(1)} c/kWh`,
      color: 'text-hot',
      bgColor: 'bg-hot/10',
    },
    {
      icon: PiggyBank,
      label: t('analytics.summary.savings'),
      value: `€${summary.totalSavings.toFixed(2)}`,
      subValue: `${summary.savingsPercent.toFixed(0)}% ${t('analytics.labels.saved')}`,
      color: 'text-success',
      bgColor: 'bg-success/10',
    },
    {
      icon: Thermometer,
      label: t('analytics.summary.avgOutdoorTemp'),
      value: `${summary.avgOutdoorTemp.toFixed(1)}°C`,
      subValue: `${t('stats.poolTemp')}: ${summary.avgPoolTemp.toFixed(1)}°C`,
      color: 'text-cold',
      bgColor: 'bg-cold/10',
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <Card key={card.label}>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-start gap-3">
              <div className={`p-2 rounded-lg ${card.bgColor}`}>
                <card.icon className={`w-5 h-5 ${card.color}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-muted-foreground truncate">{card.label}</p>
                <p className={`text-lg font-semibold ${card.color}`}>{card.value}</p>
                <p className="text-xs text-muted-foreground truncate">{card.subValue}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
