import { useMemo, useState } from 'react';
import type { RouteFeedbackPayload, RouteRecommendation, SearchRequest, TicketProvider } from '../../types';
import { searchApi } from '../../services/api';
import { getAnonymousFeedbackSessionId } from '../../services/routeExperience';
import AnimatedModal from '../common/AnimatedModal';

type RatingKey = 'overall' | 'route_reasonable' | 'cost_trustworthy' | 'transfer_clear';

const RATING_KEYS: RatingKey[] = ['overall', 'route_reasonable', 'cost_trustworthy', 'transfer_clear'];

interface RouteFeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  source: 'search' | 'ai';
  context: 'route_card' | 'ai_experience';
  searchId?: string;
  searchRequest?: Partial<SearchRequest>;
  recommendation?: RouteRecommendation;
  recommendations?: RouteRecommendation[];
  modelVersion?: string;
  datasetVersion?: string;
  clickedProvider?: TicketProvider;
  clickedSegmentIndex?: number;
  t: (key: string, params?: Record<string, string>) => string;
}

export default function RouteFeedbackModal({
  isOpen,
  onClose,
  source,
  context,
  searchId,
  searchRequest,
  recommendation,
  recommendations = [],
  modelVersion,
  datasetVersion,
  clickedProvider,
  clickedSegmentIndex,
  t,
}: RouteFeedbackModalProps) {
  const [ratings, setRatings] = useState<Record<RatingKey, number>>({
    overall: 0,
    route_reasonable: 0,
    cost_trustworthy: 0,
    transfer_clear: 0,
  });
  const [comment, setComment] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>(() => recommendation ? [recommendation.id] : []);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');

  const valid = useMemo(() => RATING_KEYS.every((key) => ratings[key] >= 1), [ratings]);

  const toggleSelected = (id: string) => {
    setSelectedIds((previous) => (
      previous.includes(id) ? previous.filter((item) => item !== id) : [...previous, id]
    ));
  };

  const submit = async () => {
    if (!valid || submitting) return;
    setSubmitting(true);
    setMessage('');
    const targetRecommendation = recommendation || recommendations.find((item) => selectedIds.includes(item.id)) || recommendations[0];
    const payload: RouteFeedbackPayload = {
      search_id: searchId || 'unknown_search',
      recommendation_id: targetRecommendation?.id || 'ai_experience',
      anonymous_session_id: getAnonymousFeedbackSessionId(),
      action: 'selected',
      source,
      feedback_context: context,
      ratings,
      selected_recommendation_ids: selectedIds,
      clicked_provider: clickedProvider,
      clicked_segment_index: clickedSegmentIndex,
      comment: comment.trim() || undefined,
      search_request: (searchRequest || {}) as Record<string, unknown>,
      recommendation: (targetRecommendation || {}) as unknown as Record<string, unknown>,
      model_version: modelVersion,
      dataset_version: datasetVersion,
    };
    try {
      await searchApi.submitRouteFeedback(payload);
      setMessage(t('routeFeedback.submitSuccess'));
      window.setTimeout(onClose, 700);
    } catch {
      setMessage(t('routeFeedback.submitFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatedModal
      isOpen={isOpen}
      overlayClassName="route-feedback-modal"
      dialogClassName="route-feedback-modal__dialog"
      ariaLabel={t('routeFeedback.title')}
      onClose={onClose}
    >
      <div className="route-feedback-modal__head">
        <h2>{context === 'ai_experience' ? t('routeFeedback.aiTitle') : t('routeFeedback.title')}</h2>
        <button type="button" className="route-feedback-modal__close" onClick={onClose}>x</button>
      </div>

      <div className={`route-feedback-modal__body ${context === 'ai_experience' && recommendations.length > 0 ? 'route-feedback-modal__body--with-choices' : ''}`}>
        <div className="route-feedback-modal__main">
          <div className="route-feedback-modal__ratings">
            {RATING_KEYS.map((key) => (
              <div key={key} className="route-feedback-modal__rating-row">
                <span>{t(`routeFeedback.ratings.${key}`)}</span>
                <div className="route-feedback-modal__stars">
                  {[1, 2, 3, 4, 5].map((value) => (
                    <button
                      key={value}
                      type="button"
                      className={value <= ratings[key] ? 'active' : ''}
                      aria-label={t('routeFeedback.starLabel', { value: String(value) })}
                      onClick={() => setRatings((previous) => ({ ...previous, [key]: value }))}
                    >
                      {'\u2605'}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <textarea
            className="route-feedback-modal__comment"
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder={t('routeFeedback.commentPlaceholder')}
            maxLength={2000}
          />
        </div>

        {context === 'ai_experience' && recommendations.length > 0 ? (
          <div className="route-feedback-modal__choices">
            <div className="route-feedback-modal__choices-title">{t('routeFeedback.selectedRoutes')}</div>
            {recommendations.map((item) => (
              <label key={item.id} className="route-feedback-modal__choice">
                <input
                  type="checkbox"
                  checked={selectedIds.includes(item.id)}
                  onChange={() => toggleSelected(item.id)}
                />
                <span>{item.city_path.join(' / ')}</span>
              </label>
            ))}
          </div>
        ) : null}
      </div>

      {message ? <div className="route-feedback-modal__message">{message}</div> : null}

      <div className="route-feedback-modal__actions">
        <button type="button" className="btn btn--secondary" onClick={onClose}>{t('routeFeedback.cancel')}</button>
        <button
          type="button"
          className="btn btn--primary route-feedback-modal__submit"
          disabled={!valid || submitting}
          onClick={submit}
        >
          {submitting ? t('routeFeedback.submitting') : t('routeFeedback.submit')}
        </button>
      </div>
    </AnimatedModal>
  );
}
